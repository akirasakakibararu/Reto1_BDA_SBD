import argparse
import csv
import json
import os
import re
import tempfile
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from scripts.procesamiento.normalizar_datos import normalize_code, parse_number
from .descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://opendata.euskadi.eus/webopd00-dataset/es/contenidos/estadistica/"
    "udalmap_indicador_61/es_def/adjuntos/indicator.shtml"
)
HTML_PATH = (
    ROOT
    / "datos"
    / "originales"
    / "ingresos"
    / "udalmap_renta_personal_disponible_municipios.html"
)
PROCESSED_INCOME_PATH = (
    ROOT / "datos" / "procesados" / "ingresos" / "udalmap_renta_municipal_anual.csv"
)
REPORT_PATH = (
    ROOT
    / "datos"
    / "procesados"
    / "ingresos"
    / "udalmap_renta_scraping_verificacion.json"
)
FUENTE = {
    "source": "Udalmap, indicador 61 - tabla HTML de renta por municipio",
    "publisher": "Gobierno Vasco; estadística subyacente de Eustat",
    "format": "HTML original (tabla municipal pública)",
    "license": "CC BY 4.0",
}
YEAR_PATTERN = re.compile(r"^\d{4}$")
CODE_PATTERN = re.compile(r"^\d{1,5}$")


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(
        self, tag: str, _attrs: list[tuple[str, str | None]]
    ) -> None:
        del _attrs
        if tag == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
        elif self._table_depth == 1:
            if tag == "tr":
                self._row = []
            elif tag in {"td", "th"} and self._row is not None:
                self._cell_parts = []
            elif tag == "br" and self._cell_parts is not None:
                self._cell_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._table_depth == 1:
            if tag in {"td", "th"} and self._cell_parts is not None:
                value = " ".join("".join(self._cell_parts).split())
                if self._row is not None:
                    self._row.append(value)
                self._cell_parts = None
            elif tag == "tr" and self._row is not None:
                if self._table is not None and self._row:
                    self._table.append(self._row)
                self._row = None
        if tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._table is not None:
                self.tables.append(self._table)
                self._table = None

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)


def parse_municipality_table(html: str) -> list[dict[str, Any]]:
    parser = _HTMLTableParser()
    parser.feed(html)
    year_indexes: dict[int, int] | None = None
    data_rows: list[list[str]] = []

    for table in parser.tables:
        for header_index, row in enumerate(table):
            headings = [" ".join(value.split()).casefold() for value in row]
            if len(headings) < 3 or headings[0] != "código municipio":
                continue
            if headings[1] != "municipio":
                continue
            detected_years = {
                int(value): index
                for index, value in enumerate(headings)
                if YEAR_PATTERN.fullmatch(value)
            }
            if 2023 in detected_years:
                year_indexes = detected_years
                data_rows = table[header_index + 1 :]
                break
        if year_indexes is not None:
            break

    if year_indexes is None:
        raise ValueError("No se encontró la tabla municipal de renta Udalmap.")

    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()
    for row in data_rows:
        if len(row) < 2 or not CODE_PATTERN.fullmatch(row[0].strip()):
            continue
        code = normalize_code(row[0])
        name = row[1].strip()
        if not name:
            raise ValueError(f"Falta el nombre municipal para el código {code}.")
        for year, column_index in year_indexes.items():
            if column_index >= len(row):
                raise ValueError(
                    f"Fila municipal incompleta para {code}, año {year}."
                )
            key = (code, year)
            if key in seen_keys:
                raise ValueError(f"Registro municipal duplicado en el HTML: {key}.")
            seen_keys.add(key)
            records.append(
                {
                    "municipality_code": code,
                    "municipality_name": name,
                    "year": year,
                    "available_income_eur": parse_number(row[column_index]),
                }
            )

    if not records:
        raise ValueError("La tabla HTML no contiene registros municipales.")
    return records


def _read_processed_income() -> dict[tuple[str, int], Decimal | None]:
    if not PROCESSED_INCOME_PATH.is_file():
        raise FileNotFoundError(
            "Primero ejecute scripts.procesamiento.normalizar_datos."
        )
    records: dict[tuple[str, int], Decimal | None] = {}
    with PROCESSED_INCOME_PATH.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            key = (normalize_code(row["municipality_code"]), int(row["year"]))
            if key in records:
                raise ValueError(f"Registro duplicado en el CSV procesado: {key}.")
            records[key] = parse_number(row["available_income_eur"])
    return records


def _record_value(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=REPORT_PATH.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(report, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, REPORT_PATH)
        temporary_path = None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga y extrae la tabla HTML oficial de renta Udalmap; "
            "la contrasta con el CSV ya normalizado."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vuelve a descargar y sustituye el HTML local.",
    )
    args = parser.parse_args()
    logger = configurar_logging()
    metadata = descargar_archivo(URL, HTML_PATH, FUENTE, forzar=args.force)
    content_type = metadata.get("content_type") or ""
    charset_match = re.search(r"charset=([^;]+)", content_type, flags=re.IGNORECASE)
    encoding = charset_match.group(1).strip().strip('"') if charset_match else "utf-8"
    html = HTML_PATH.read_text(encoding=encoding)
    scraped_records = parse_municipality_table(html)
    processed_values = _read_processed_income()
    scraped_values = {
        (row["municipality_code"], row["year"]): row["available_income_eur"]
        for row in scraped_records
    }

    missing_from_scrape = sorted(set(processed_values) - set(scraped_values))
    missing_from_csv = sorted(set(scraped_values) - set(processed_values))
    mismatches = [
        {
            "municipality_code": code,
            "year": year,
            "html_value": _record_value(scraped_values[(code, year)]),
            "csv_value": _record_value(processed_values[(code, year)]),
        }
        for code, year in sorted(set(scraped_values) & set(processed_values))
        if scraped_values[(code, year)] != processed_values[(code, year)]
    ]
    report = {
        "status": (
            "verified"
            if not missing_from_scrape and not missing_from_csv and not mismatches
            else "mismatch"
        ),
        "source_url": URL,
        "source_file": str(HTML_PATH.relative_to(ROOT)),
        "source_sha256": metadata["sha256"],
        "municipalities_scraped": len(
            {row["municipality_code"] for row in scraped_records}
        ),
        "records_scraped": len(scraped_records),
        "records_compared": len(set(scraped_values) & set(processed_values)),
        "missing_from_scrape": [
            {"municipality_code": code, "year": year}
            for code, year in missing_from_scrape
        ],
        "missing_from_csv": [
            {"municipality_code": code, "year": year}
            for code, year in missing_from_csv
        ],
        "mismatches": mismatches,
        "records": [
            {
                **row,
                "available_income_eur": _record_value(
                    row["available_income_eur"]
                ),
            }
            for row in scraped_records
        ],
        "output_file": str(REPORT_PATH.relative_to(ROOT)),
    }
    _write_report(report)
    if report["status"] != "verified":
        raise RuntimeError(
            "La tabla HTML no coincide con el CSV procesado; "
            f"revise {REPORT_PATH} antes de usarla."
        )
    logger.info(
        "Scraping Udalmap verificado: %d municipios, %d registros coincidentes.",
        report["municipalities_scraped"],
        report["records_compared"],
    )


if __name__ == "__main__":
    main()
