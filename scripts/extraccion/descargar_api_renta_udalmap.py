import argparse
import csv
import json
import os
import re
import tempfile
from decimal import Decimal
from typing import Any

from scripts.procesamiento.normalizar_datos import normalize_code, parse_number
from .descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://api.euskadi.eus/udalmap/indicators/61/municipalities"
    "?lang=SPANISH"
)
API_PATH = (
    ROOT
    / "datos"
    / "originales"
    / "ingresos"
    / "udalmap_renta_personal_disponible_api.json"
)
PROCESSED_INCOME_PATH = (
    ROOT / "datos" / "procesados" / "ingresos" / "udalmap_renta_municipal_anual.csv"
)
REPORT_PATH = (
    ROOT
    / "datos"
    / "procesados"
    / "ingresos"
    / "udalmap_renta_api_verificacion.json"
)
FUENTE = {
    "source": "Udalmap REST API, indicador 61 - renta personal disponible",
    "publisher": "Gobierno Vasco; estadística subyacente de Eustat",
    "format": "JSON original de API REST",
    "license": "CC BY 4.0",
}
YEAR_PATTERN = re.compile(r"^\d{4}$")


def parse_api_response(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or str(payload.get("id")) != "61":
        raise ValueError("La respuesta API no corresponde al indicador Udalmap 61.")
    municipalities = payload.get("municipalities")
    if not isinstance(municipalities, list):
        raise ValueError("La respuesta API no contiene la lista de municipios.")

    records: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_keys: set[tuple[str, int]] = set()
    for municipality in municipalities:
        if not isinstance(municipality, dict):
            raise ValueError("La respuesta API contiene un municipio no válido.")
        code = normalize_code(municipality.get("id"))
        name = str(municipality.get("name", "")).strip()
        if not name:
            raise ValueError(f"Falta el nombre municipal para el código {code}.")
        if code in seen_codes:
            raise ValueError(f"Código municipal duplicado en la API: {code}.")
        seen_codes.add(code)

        year_groups = municipality.get("years")
        if not isinstance(year_groups, list):
            raise ValueError(f"La API no contiene años para el municipio {code}.")
        for year_group in year_groups:
            if not isinstance(year_group, dict):
                raise ValueError(f"Bloque de años no válido para el municipio {code}.")
            for year_text, raw_value in year_group.items():
                if not YEAR_PATTERN.fullmatch(str(year_text)):
                    raise ValueError(
                        f"Año no válido para el municipio {code}: {year_text!r}."
                    )
                year = int(year_text)
                key = (code, year)
                if key in seen_keys:
                    raise ValueError(f"Registro municipal duplicado en la API: {key}.")
                seen_keys.add(key)
                records.append(
                    {
                        "municipality_code": code,
                        "municipality_name": name,
                        "year": year,
                        "available_income_eur": parse_number(raw_value),
                    }
                )
    if not records:
        raise ValueError("La respuesta API no contiene valores municipales.")
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
            "Descarga el indicador 61 desde la API oficial de Udalmap "
            "y lo contrasta con el CSV normalizado."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vuelve a consultar la API y sustituye el JSON local.",
    )
    args = parser.parse_args()
    logger = configurar_logging()
    metadata = descargar_archivo(URL, API_PATH, FUENTE, forzar=args.force)
    payload = json.loads(API_PATH.read_text(encoding="utf-8"))
    api_records = parse_api_response(payload)
    processed_values = _read_processed_income()
    api_values = {
        (row["municipality_code"], row["year"]): row["available_income_eur"]
        for row in api_records
    }

    missing_from_api = sorted(set(processed_values) - set(api_values))
    missing_from_csv = sorted(set(api_values) - set(processed_values))
    expected_null_omissions = [
        key for key in missing_from_api if processed_values[key] is None
    ]
    unexpected_missing_from_api = [
        key for key in missing_from_api if processed_values[key] is not None
    ]
    mismatches = [
        {
            "municipality_code": code,
            "year": year,
            "api_value": _record_value(api_values[(code, year)]),
            "csv_value": _record_value(processed_values[(code, year)]),
        }
        for code, year in sorted(set(api_values) & set(processed_values))
        if api_values[(code, year)] != processed_values[(code, year)]
    ]
    report = {
        "status": (
            "verified"
            if not missing_from_csv
            and not unexpected_missing_from_api
            and not mismatches
            else "mismatch"
        ),
        "api_url": URL,
        "api_specification": (
            "https://opendata.euskadi.eus/contenidos/recurso_tecnico/"
            "data_apirest/es_def/adjuntos/udalmap.json"
        ),
        "source_file": str(API_PATH.relative_to(ROOT)),
        "source_sha256": metadata["sha256"],
        "municipalities_returned": len(
            {row["municipality_code"] for row in api_records}
        ),
        "records_returned": len(api_records),
        "records_compared": len(set(api_values) & set(processed_values)),
        "expected_null_omissions": [
            {
                "municipality_code": code,
                "year": year,
                "csv_value": None,
            }
            for code, year in expected_null_omissions
        ],
        "unexpected_missing_from_api": [
            {"municipality_code": code, "year": year}
            for code, year in unexpected_missing_from_api
        ],
        "missing_from_csv": [
            {"municipality_code": code, "year": year}
            for code, year in missing_from_csv
        ],
        "mismatches": mismatches,
        "output_file": str(REPORT_PATH.relative_to(ROOT)),
    }
    _write_report(report)
    if report["status"] != "verified":
        raise RuntimeError(
            "La API de Udalmap no coincide con el CSV procesado; "
            f"revise {REPORT_PATH} antes de usarla."
        )
    logger.info(
        "API Udalmap verificada: %d municipios, %d observaciones comparadas, "
        "%d ausencia(s) nula(s) esperada(s).",
        report["municipalities_returned"],
        report["records_compared"],
        len(expected_null_omissions),
    )


if __name__ == "__main__":
    main()
