import csv
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from scripts.extraccion.descarga_comun import ROOT, configurar_logging


PDF_PATH = (
    ROOT
    / "datos"
    / "originales"
    / "juventud"
    / "indicadores_de_juventud_2025.pdf"
)
SALARY_PATH = (
    ROOT
    / "datos"
    / "procesados"
    / "ingresos"
    / "salarios_juveniles_observatorio.csv"
)
REFERENCE_PATH = (
    ROOT
    / "datos"
    / "procesados"
    / "ingresos"
    / "referencias_juveniles_observatorio.csv"
)
YEAR_PATTERN = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
VALUE_PATTERN = re.compile(r"\d+(?:[.,]\d+)*")

SALARY_DIMENSIONS = {
    "total": ("euskadi", None, "Euskadi", "18-34", "total"),
    "male": ("euskadi", None, "Euskadi", "18-34", "male"),
    "female": ("euskadi", None, "Euskadi", "18-34", "female"),
    "alava": ("territory", "01", "Álava", "18-34", "total"),
    "bizkaia": ("territory", "48", "Bizkaia", "18-34", "total"),
    "gipuzkoa": ("territory", "20", "Gipuzkoa", "18-34", "total"),
    "age_18_29": ("euskadi", None, "Euskadi", "18-29", "total"),
    "age_30_34": ("euskadi", None, "Euskadi", "30-34", "total"),
    "spain_18_34": ("country", None, "España", "18-34", "total"),
}
ACCESS_DIMENSIONS = {
    "total": ("euskadi", None, "Euskadi", "18-34", "total"),
    "male": ("euskadi", None, "Euskadi", "18-34", "male"),
    "female": ("euskadi", None, "Euskadi", "18-34", "female"),
    "age_18_24": ("euskadi", None, "Euskadi", "18-24", "total"),
    "age_25_29": ("euskadi", None, "Euskadi", "25-29", "total"),
    "age_18_29": ("euskadi", None, "Euskadi", "18-29", "total"),
    "age_30_34": ("euskadi", None, "Euskadi", "30-34", "total"),
    "alava": ("territory", "01", "Álava", "18-34", "total"),
    "bizkaia": ("territory", "48", "Bizkaia", "18-34", "total"),
    "gipuzkoa": ("territory", "20", "Gipuzkoa", "18-34", "total"),
}
PERSONAL_INCOME_DIMENSIONS = {
    "total": ("euskadi", None, "Euskadi", "25-29", "total"),
    "male": ("euskadi", None, "Euskadi", "25-29", "male"),
    "female": ("euskadi", None, "Euskadi", "25-29", "female"),
}

SALARY_FIELDS = [
    "indicator_code",
    "year",
    "geography_level",
    "territory_code",
    "territory_name",
    "age_group",
    "sex",
    "net_monthly_salary_eur",
    "unit",
    "source_page",
    "source_row",
]
REFERENCE_FIELDS = [
    "indicator_code",
    "year",
    "geography_level",
    "territory_code",
    "territory_name",
    "age_group",
    "sex",
    "metric",
    "value",
    "unit",
    "source_page",
    "source_row",
]


def _ascii_key(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )


def _row_key(tokens: list[str]) -> tuple[str | None, int]:
    if not tokens:
        return None, 0
    first = _ascii_key(tokens[0])
    if first.startswith("18-24"):
        return "age_18_24", 2
    if first.startswith("18-29"):
        return "age_18_29", 2
    if first.startswith("25-29"):
        return "age_25_29", 2
    if first.startswith("30-34"):
        return "age_30_34", 2
    if first.startswith("total"):
        return "total", 1
    if first.startswith("hombres"):
        return "male", 1
    if first.startswith("mujeres"):
        return "female", 1
    if first.startswith("alava") or first == "lava":
        return "alava", 1
    if first.startswith("bizkaia"):
        return "bizkaia", 1
    if first.startswith("gipuzkoa"):
        return "gipuzkoa", 1
    if first.startswith("espana"):
        return "spain_18_34", 3
    return None, 0


def _parse_spanish_number(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def parse_indicator_table(
    page_text: str, dimensions: dict[str, tuple[str, str | None, str, str, str]]
) -> tuple[list[int], dict[str, list[Decimal]]]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    header_index: int | None = None
    years: list[int] = []
    for index, line in enumerate(lines):
        candidate = [int(year) for year in YEAR_PATTERN.findall(line)]
        if len(candidate) >= 2:
            header_index = index
            years = candidate
            break
    if header_index is None:
        raise ValueError("No se encontró la cabecera anual del indicador.")

    parsed_rows: dict[str, list[Decimal]] = {}
    for line in lines[header_index + 1 :]:
        tokens = line.split()
        key, label_token_count = _row_key(tokens)
        if key is None or key not in dimensions:
            continue
        if key in parsed_rows:
            raise ValueError(f"Fila repetida en la tabla del indicador: {key}")
        values = [
            _parse_spanish_number(token)
            for token in VALUE_PATTERN.findall(
                " ".join(tokens[label_token_count:])
            )
        ]
        if len(values) != len(years):
            raise ValueError(
                f"La fila {key} contiene {len(values)} valores; "
                f"se esperaban {len(years)}."
            )
        parsed_rows[key] = values

    missing_rows = set(dimensions) - parsed_rows.keys()
    if missing_rows:
        raise ValueError(
            "Faltan filas publicadas del indicador: "
            + ", ".join(sorted(missing_rows))
        )
    return years, parsed_rows


def _find_indicator_page(reader: PdfReader, indicator_code: int) -> tuple[int, str]:
    marker = f"Indicador {indicator_code}:"
    for page_index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        has_year_header = any(
            len(YEAR_PATTERN.findall(line)) >= 2 for line in text.splitlines()
        )
        if marker in text and has_year_header:
            return page_index + 1, text
    raise ValueError(f"No se encontró el indicador {indicator_code} en el PDF.")


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


def _build_rows(
    indicator_code: int,
    years: list[int],
    parsed: dict[str, list[Decimal]],
    dimensions: dict[str, tuple[str, str | None, str, str, str]],
    *,
    source_page: int,
    metric: str,
    unit: str,
) -> list[dict[str, Any]]:
    rows = []
    for key, values in parsed.items():
        geography_level, territory_code, territory_name, age_group, sex = (
            dimensions[key]
        )
        for year, value in zip(years, values, strict=True):
            row = {
                "indicator_code": indicator_code,
                "year": year,
                "geography_level": geography_level,
                "territory_code": territory_code or "",
                "territory_name": territory_name,
                "age_group": age_group,
                "sex": sex,
                "metric": metric,
                "value": _format_decimal(value),
                "unit": unit,
                "source_page": source_page,
                "source_row": key,
            }
            rows.append(row)
    return rows


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=fields,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def extract_indicator_rows(pdf_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise FileNotFoundError(f"No existe el PDF oficial o está vacío: {pdf_path}")
    reader = PdfReader(str(pdf_path))
    salary_page, salary_text = _find_indicator_page(reader, 31)
    income_page, income_text = _find_indicator_page(reader, 32)
    access_page, access_text = _find_indicator_page(reader, 49)

    salary_years, salary_values = parse_indicator_table(
        salary_text, SALARY_DIMENSIONS
    )
    income_years, income_values = parse_indicator_table(
        income_text, PERSONAL_INCOME_DIMENSIONS
    )
    access_years, access_values = parse_indicator_table(
        access_text, ACCESS_DIMENSIONS
    )

    if salary_years != list(range(2010, 2025)):
        raise ValueError(f"Periodo inesperado para el indicador 31: {salary_years}")
    if income_years != list(range(2013, 2024)):
        raise ValueError(f"Periodo inesperado para el indicador 32: {income_years}")
    if access_years != list(range(2016, 2025)):
        raise ValueError(f"Periodo inesperado para el indicador 49: {access_years}")

    salary_rows = _build_rows(
        31,
        salary_years,
        salary_values,
        SALARY_DIMENSIONS,
        source_page=salary_page,
        metric="net_monthly_salary",
        unit="EUR/month",
    )
    reference_rows = _build_rows(
        32,
        income_years,
        income_values,
        PERSONAL_INCOME_DIMENSIONS,
        source_page=income_page,
        metric="personal_income_annual",
        unit="EUR/year",
    ) + _build_rows(
        49,
        access_years,
        access_values,
        ACCESS_DIMENSIONS,
        source_page=access_page,
        metric="rent_access_percent",
        unit="percent",
    )
    _verify_published_values(salary_rows, reference_rows)
    return salary_rows, reference_rows


def _verify_published_values(
    salary_rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]]
) -> None:
    salary_expected = {
        ("territory", "01", "18-34", "total"): Decimal("1487"),
        ("territory", "48", "18-34", "total"): Decimal("1585"),
        ("territory", "20", "18-34", "total"): Decimal("1555"),
        ("euskadi", "", "18-29", "total"): Decimal("1381"),
        ("euskadi", "", "30-34", "total"): Decimal("1774"),
    }
    for row in salary_rows:
        if row["year"] != 2024:
            continue
        key = (
            row["geography_level"],
            row["territory_code"],
            row["age_group"],
            row["sex"],
        )
        if key in salary_expected and Decimal(row["value"]) != salary_expected[key]:
            raise ValueError(
                f"El valor oficial del indicador 31 no coincide para {key}: "
                f"{row['value']}."
            )
    benchmark_expected = {
        (49, "territory", "01", "18-34", "total"): Decimal("50.2"),
        (49, "territory", "48", "18-34", "total"): Decimal("51.4"),
        (49, "territory", "20", "18-34", "total"): Decimal("54.9"),
        (49, "euskadi", "", "18-29", "total"): Decimal("59.4"),
        (49, "euskadi", "", "30-34", "total"): Decimal("46.2"),
        (32, "euskadi", "", "25-29", "total"): Decimal("17930"),
    }
    for row in reference_rows:
        if row["year"] != (2023 if row["indicator_code"] == 32 else 2024):
            continue
        key = (
            row["indicator_code"],
            row["geography_level"],
            row["territory_code"],
            row["age_group"],
            row["sex"],
        )
        if key in benchmark_expected and Decimal(row["value"]) != benchmark_expected[key]:
            raise ValueError(
                f"El valor oficial no coincide para el indicador {key[0]} {key[1:]}: "
                f"{row['value']}."
            )


def main() -> None:
    logger = configurar_logging()
    salary_rows, reference_rows = extract_indicator_rows(PDF_PATH)
    salary_output = [
        {
            "indicator_code": row["indicator_code"],
            "year": row["year"],
            "geography_level": row["geography_level"],
            "territory_code": row["territory_code"],
            "territory_name": row["territory_name"],
            "age_group": row["age_group"],
            "sex": row["sex"],
            "net_monthly_salary_eur": row["value"],
            "unit": row["unit"],
            "source_page": row["source_page"],
            "source_row": row["source_row"],
        }
        for row in salary_rows
    ]
    _write_csv(SALARY_PATH, SALARY_FIELDS, salary_output)
    _write_csv(REFERENCE_PATH, REFERENCE_FIELDS, reference_rows)
    logger.info(
        "Extraídos %s salarios y %s referencias de los indicadores 32 y 49.",
        len(salary_output),
        len(reference_rows),
    )
    print(
        f"Datos juveniles procesados: {len(salary_output)} salarios, "
        f"{len(reference_rows)} referencias."
    )


if __name__ == "__main__":
    main()
