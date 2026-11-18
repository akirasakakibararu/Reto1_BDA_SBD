import csv
import json
import logging
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[2]
ORIGINALS = ROOT / "datos" / "originales"
PROCESSED = ROOT / "datos" / "procesados"
CODE_PATTERN = re.compile(r"^\d{5}$")
YEAR_PATTERN = re.compile(r"^\d{4}$")
MISSING_VALUES = {"", "-", "–", "—", "NA", "N/A", "n.d."}
TERRITORIES = {
    "01": "Araba/Álava",
    "20": "Gipuzkoa",
    "48": "Bizkaia",
}


def normalize_code(value: Any) -> str:
    if value is None:
        raise ValueError("El código municipal está vacío.")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    code = str(value).strip()
    if not code.isdigit() or len(code) > 5:
        raise ValueError(f"Código municipal no válido: {value!r}")
    code = code.zfill(5)
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError(f"Código municipal no válido: {value!r}")
    return code


def parse_number(value: Any, *, integer: bool = False) -> Decimal | int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in MISSING_VALUES:
            return None
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"Valor numérico no válido: {value!r}") from error
    if not number.is_finite():
        raise ValueError(f"Valor numérico no finito: {value!r}")
    if integer:
        if number != number.to_integral_value():
            raise ValueError(f"Se esperaba un entero y se recibió {value!r}")
        return int(number)
    return number


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(
                temporary_file,
                fieldnames=fieldnames,
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: format(value, "f") if isinstance(value, Decimal) else value
                        for key, value in row.items()
                    }
                )
        temporary_path.replace(path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _read_emal(workbook_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheets = {
        "T2.1": ("deposit_count", True),
        "T2.2": ("monthly_rent_eur", False),
        "T2.3": ("rent_per_m2_eur", False),
    }
    joined: dict[tuple[str, str, int], dict[str, Any]] = {}
    source_keys: dict[str, set[tuple[str, str, int]]] = {}

    try:
        for sheet_name, (metric, is_integer) in sheets.items():
            if sheet_name not in workbook.sheetnames:
                raise ValueError(f"Falta la hoja EMAL esperada: {sheet_name}")
            worksheet = workbook[sheet_name]
            year_columns: list[tuple[int, int]] = []
            for column_index, value in enumerate(
                next(worksheet.iter_rows(min_row=2, max_row=2, values_only=True))
            ):
                if column_index >= 2 and value is not None:
                    year_text = str(value).strip()
                    if YEAR_PATTERN.fullmatch(year_text):
                        year_columns.append((column_index, int(year_text)))
            if not year_columns:
                raise ValueError(f"No se encontraron años en la hoja {sheet_name}.")

            keys: set[tuple[str, str, int]] = set()
            for excel_row, row in enumerate(
                worksheet.iter_rows(min_row=5, values_only=True), start=5
            ):
                raw_code = row[0] if row else None
                if raw_code is None or not str(raw_code).strip().isdigit():
                    continue
                code = normalize_code(raw_code)
                raw_name = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                if not raw_name:
                    raise ValueError(
                        f"Falta el nombre municipal en {sheet_name}, fila {excel_row}."
                    )

                name = raw_name
                variant = "municipality"
                current_boundary = True
                if code == "48036" and raw_name.endswith("(1)"):
                    name = raw_name[:-3].strip()
                    variant = "current_excluding_usansolo"
                elif code == "48036" and raw_name.endswith("(2)"):
                    name = raw_name[:-3].strip()
                    variant = "historical_including_usansolo"
                    current_boundary = False

                for column_index, year in year_columns:
                    key = (code, variant, year)
                    if key in keys:
                        raise ValueError(
                            f"Clave municipal/año duplicada en {sheet_name}: {key}"
                        )
                    keys.add(key)
                    record = joined.setdefault(
                        key,
                        {
                            "municipality_code": code,
                            "municipality_name": name,
                            "municipality_name_source": raw_name,
                            "geography_variant": variant,
                            "included_in_current_boundary_comparison": current_boundary,
                            "year": year,
                            "rent_reference": "EMAL contract start year",
                            "historical_rent_adjustment_note": (
                                "Historical rents may be updated using IRAV; "
                                "published figures may be provisional."
                            ),
                        },
                    )
                    if record["municipality_name_source"] != raw_name:
                        raise ValueError(
                            f"Nombre fuente inconsistente para {key}: "
                            f"{record['municipality_name_source']!r} y {raw_name!r}"
                        )
                    record[metric] = parse_number(
                        row[column_index] if column_index < len(row) else None,
                        integer=is_integer,
                    )
                    record[f"source_row_{sheet_name}"] = excel_row
            source_keys[sheet_name] = keys
    finally:
        workbook.close()

    if not joined:
        raise ValueError("No se encontraron filas municipales en el libro EMAL.")

    key_sets = list(source_keys.values())
    mismatched_keys = {
        sheet: {
            "missing_from_sheet": sorted(set.union(*key_sets) - keys),
            "extra_in_sheet": sorted(keys - set.intersection(*key_sets)),
        }
        for sheet, keys in source_keys.items()
        if keys != set.intersection(*key_sets)
    }
    for row in joined.values():
        row["source_workbook"] = "emal_alquiler_municipios_2016-2026T1.xlsx"
        row["source_sheets"] = "T2.1;T2.2;T2.3"

    ordered = sorted(
        joined.values(),
        key=lambda item: (
            item["municipality_code"],
            item["geography_variant"],
            item["year"],
        ),
    )
    return ordered, {
        "source_sheets": {
            sheet: len(keys) for sheet, keys in source_keys.items()
        },
        "sheet_key_mismatches": mismatched_keys,
    }


def _find_udalmap_header(rows: list[list[str]], path: Path) -> int:
    for index, row in enumerate(rows):
        if (
            len(row) >= 3
            and row[0].strip().casefold() == "código municipio"
            and row[1].strip().casefold() == "municipio"
        ):
            return index
    raise ValueError(f"No se encontró la cabecera municipal de Udalmap en {path}.")


def _read_udalmap(
    path: Path,
    *,
    value_field: str,
    integer: bool,
    units: str,
    scope: str,
) -> list[dict[str, Any]]:
    with path.open(encoding="cp1252", newline="") as source_file:
        rows = list(csv.reader(source_file, delimiter=";"))
    header_index = _find_udalmap_header(rows, path)
    header = rows[header_index]
    year_columns = [
        (index, int(value.strip()))
        for index, value in enumerate(header[2:], start=2)
        if YEAR_PATTERN.fullmatch(value.strip())
    ]
    if not year_columns:
        raise ValueError(f"No se encontraron años en la cabecera de {path}.")
    if len({year for _, year in year_columns}) != len(year_columns):
        raise ValueError(f"Hay años duplicados en la cabecera de {path}.")

    municipality_names: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or not row[0].strip():
            continue
        raw_code = row[0].strip()
        if not CODE_PATTERN.fullmatch(raw_code):
            raise ValueError(
                f"Código inesperado en {path.name}, fila {row_number}: {raw_code!r}"
            )
        code = normalize_code(raw_code)
        name = row[1].strip() if len(row) > 1 else ""
        if not name:
            raise ValueError(
                f"Falta el nombre municipal en {path.name}, fila {row_number}."
            )
        if code in municipality_names:
            raise ValueError(f"Código municipal duplicado en {path.name}: {code}")
        municipality_names[code] = name

        for column_index, year in year_columns:
            raw_value = row[column_index] if column_index < len(row) else None
            records.append(
                {
                    "municipality_code": code,
                    "municipality_name": name,
                    "year": year,
                    value_field: parse_number(raw_value, integer=integer),
                    "units": units,
                    "population_scope": scope,
                    "source_file": path.name,
                    "source_row": row_number,
                }
            )
    if not municipality_names:
        raise ValueError(f"No se encontraron municipios en {path}.")
    return records


def _validate_records(
    name: str,
    records: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    required_fields: tuple[str, ...],
    metric_fields: tuple[str, ...],
) -> dict[str, Any]:
    keys: set[tuple[Any, ...]] = set()
    duplicate_keys: list[tuple[Any, ...]] = []
    missing_required = 0
    null_metrics = {field: 0 for field in metric_fields}
    for row in records:
        key = tuple(row[field] for field in key_fields)
        if key in keys:
            duplicate_keys.append(key)
        keys.add(key)
        if any(row.get(field) in (None, "") for field in required_fields):
            missing_required += 1
        for field in metric_fields:
            if row.get(field) is None:
                null_metrics[field] += 1

    if duplicate_keys:
        raise ValueError(f"{name}: claves duplicadas: {duplicate_keys[:5]}")
    if missing_required:
        raise ValueError(f"{name}: {missing_required} registros sin campos obligatorios.")
    years = [int(row["year"]) for row in records]
    codes = {row["municipality_code"] for row in records}
    return {
        "records": len(records),
        "municipalities": len(codes),
        "year_min": min(years),
        "year_max": max(years),
        "duplicate_keys": len(duplicate_keys),
        "records_missing_required_fields": missing_required,
        "null_metrics": null_metrics,
        "null_metric_examples": {
            field: [
                {
                    "municipality_code": row["municipality_code"],
                    "municipality_name": row["municipality_name"],
                    "year": row["year"],
                }
                for row in records
                if row.get(field) is None
            ][:10]
            for field in metric_fields
        },
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "logs" / "procesamiento.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("reto_vivienda.procesamiento")

    rental_path = (
        ORIGINALS
        / "alquiler"
        / "emal_alquiler_municipios_2016-2026T1.xlsx"
    )
    income_path = (
        ORIGINALS / "ingresos" / "udalmap_renta_personal_disponible.csv"
    )
    population_path = ORIGINALS / "poblacion" / "udalmap_poblacion_total.csv"
    for path in (rental_path, income_path, population_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"No existe el original o está vacío: {path}")

    rental_rows, emal_structure = _read_emal(rental_path)
    income_rows = _read_udalmap(
        income_path,
        value_field="available_income_eur",
        integer=False,
        units="EUR per resident aged 18+",
        scope="mean available personal income; not a youth salary",
    )
    population_rows = _read_udalmap(
        population_path,
        value_field="population",
        integer=True,
        units="inhabitants",
        scope="total municipal population",
    )

    income_codes = {row["municipality_code"] for row in income_rows}
    population_codes = {row["municipality_code"] for row in population_rows}
    rental_codes = {
        row["municipality_code"]
        for row in rental_rows
        if row["included_in_current_boundary_comparison"]
    }
    if income_codes != population_codes:
        raise ValueError(
            "Los códigos municipales de renta y población no coinciden: "
            f"solo renta={sorted(income_codes - population_codes)}, "
            f"solo población={sorted(population_codes - income_codes)}"
        )
    unknown_prefixes = sorted(
        {code[:2] for code in population_codes} - set(TERRITORIES)
    )
    if unknown_prefixes:
        raise ValueError(f"Prefijos territoriales no reconocidos: {unknown_prefixes}")

    income_by_code_year = {
        (row["municipality_code"], row["year"]): row["available_income_eur"]
        for row in income_rows
    }
    population_by_code_year = {
        (row["municipality_code"], row["year"]): row["population"]
        for row in population_rows
    }
    latest_common_year = min(
        max(row["year"] for row in rental_rows),
        max(row["year"] for row in income_rows),
        max(row["year"] for row in population_rows),
    )
    joined_codes = {
        row["municipality_code"]
        for row in rental_rows
        if row["year"] == latest_common_year
        and row["included_in_current_boundary_comparison"]
        and row.get("monthly_rent_eur") is not None
        and income_by_code_year.get((row["municipality_code"], latest_common_year))
        is not None
        and population_by_code_year.get((row["municipality_code"], latest_common_year))
        is not None
    }

    municipalities: dict[str, dict[str, Any]] = {}
    for row in population_rows:
        code = row["municipality_code"]
        municipality = municipalities.setdefault(
            code,
            {
                "municipality_code": code,
                "municipality_name": row["municipality_name"],
                "territory_code": code[:2],
                "territory_name": TERRITORIES[code[:2]],
            },
        )
        if municipality["municipality_name"] != row["municipality_name"]:
            raise ValueError(f"Nombre inconsistente por año para {code}.")

    rental_report = _validate_records(
        "EMAL alquiler",
        rental_rows,
        ("municipality_code", "geography_variant", "year"),
        ("municipality_code", "municipality_name", "year"),
        ("deposit_count", "monthly_rent_eur", "rent_per_m2_eur"),
    )
    income_report = _validate_records(
        "Udalmap renta",
        income_rows,
        ("municipality_code", "year"),
        ("municipality_code", "municipality_name", "year"),
        ("available_income_eur",),
    )
    population_report = _validate_records(
        "Udalmap población",
        population_rows,
        ("municipality_code", "year"),
        ("municipality_code", "municipality_name", "year"),
        ("population",),
    )

    rental_fields = [
        "municipality_code",
        "municipality_name",
        "municipality_name_source",
        "geography_variant",
        "included_in_current_boundary_comparison",
        "year",
        "deposit_count",
        "monthly_rent_eur",
        "rent_per_m2_eur",
        "rent_reference",
        "historical_rent_adjustment_note",
        "source_workbook",
        "source_sheets",
        "source_row_T2.1",
        "source_row_T2.2",
        "source_row_T2.3",
    ]
    income_fields = [
        "municipality_code",
        "municipality_name",
        "year",
        "available_income_eur",
        "units",
        "population_scope",
        "source_file",
        "source_row",
    ]
    population_fields = [
        "municipality_code",
        "municipality_name",
        "year",
        "population",
        "units",
        "population_scope",
        "source_file",
        "source_row",
    ]
    output_paths = {
        "rent": PROCESSED / "alquiler" / "emal_alquiler_municipal_anual.csv",
        "income": PROCESSED / "ingresos" / "udalmap_renta_municipal_anual.csv",
        "population": PROCESSED / "poblacion" / "udalmap_poblacion_municipal_anual.csv",
        "municipalities": PROCESSED / "municipios_referencia.csv",
        "validation": PROCESSED / "validacion_datos.json",
    }
    write_csv_atomic(output_paths["rent"], rental_fields, rental_rows)
    write_csv_atomic(output_paths["income"], income_fields, income_rows)
    write_csv_atomic(output_paths["population"], population_fields, population_rows)
    write_csv_atomic(
        output_paths["municipalities"],
        [
            "municipality_code",
            "municipality_name",
            "territory_code",
            "territory_name",
        ],
        sorted(municipalities.values(), key=lambda item: item["municipality_code"]),
    )

    metadata_files = {
        "rent": rental_path.with_suffix(rental_path.suffix + ".metadata.json"),
        "income": income_path.with_suffix(income_path.suffix + ".metadata.json"),
        "population": population_path.with_suffix(population_path.suffix + ".metadata.json"),
    }
    source_metadata = {
        name: {
            key: value
            for key, value in json.loads(path.read_text(encoding="utf-8")).items()
            if key in {"url", "downloaded_at_utc", "http_status", "content_length", "sha256"}
        }
        for name, path in metadata_files.items()
    }
    validation = {
        "status": "passed",
        "source_metadata": source_metadata,
        "source_files": {
            "rent": rental_path.name,
            "income": income_path.name,
            "population": population_path.name,
        },
        "datasets": {
            "rent": rental_report,
            "income": income_report,
            "population": population_report,
        },
        "emal_table_structure": emal_structure,
        "municipal_code_coverage": {
            "current_emal_municipalities": len(rental_codes),
            "income_municipalities": len(income_codes),
            "population_municipalities": len(population_codes),
            "emal_codes_without_income": sorted(rental_codes - income_codes),
            "emal_codes_without_population": sorted(rental_codes - population_codes),
            "income_codes_without_emal_count": len(income_codes - rental_codes),
            "income_codes_without_emal_sample": sorted(income_codes - rental_codes)[:10],
        },
        "latest_common_year_with_rent_income_and_population": latest_common_year,
        "complete_comparison_municipalities_in_latest_common_year": len(joined_codes),
        "comparison_codes_missing_from_latest_common_year": sorted(
            rental_codes - joined_codes
        ),
        "galdakao_geographies": {
            "retained": [
                "Current Galdakao excluding Usansolo",
                "Historical Galdakao including Usansolo",
            ],
            "historical_variant_in_current_boundary_comparison": False,
        },
        "transformations": [
            "Municipal codes normalized to five-character text.",
            "Udalmap CSV parsed as semicolon-delimited cp1252 with Spanish decimal notation.",
            "EMAL annual sheets T2.1, T2.2, and T2.3 joined by municipality, geography variant, and year.",
            "Missing metric values preserved as empty fields; no imputation or geographic allocation.",
            "Historical Galdakao including Usansolo retained but excluded from current-boundary comparisons.",
        ],
        "limitations": [
            "Udalmap available personal income is a mean for residents aged 18+; it is not a youth wage or an individual salary.",
            "EMAL values are identified by contract start year; historical values may be updated using IRAV and may be provisional.",
            "The 2023 comparison aligns the published year labels, but does not make the measures equivalent to a contemporaneous net wage and rent.",
            "Rental coverage is limited to EMAL-published municipalities; no values are distributed to municipalities without rental data.",
        ],
    }
    output_paths["validation"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["validation"].write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Procesamiento y validación completados: %s", output_paths["validation"])
    logger.info("Municipios con datos completos en %s: %s", latest_common_year, len(joined_codes))


if __name__ == "__main__":
    main()
