import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests

from scripts.extraccion.descarga_comun import ROOT, configurar_logging


PORTAL_URL = (
    "https://www.gazteaukera.euskadi.eus/webgaz00-ovjstat/es/"
    "ae29aConsultaWar"
)
API_URL = f"{PORTAL_URL}/indicadornum/cogerDatosTabla"
ORIGINALS = ROOT / "datos" / "originales" / "juventud"
REPORT_PATH = (
    ROOT
    / "datos"
    / "procesados"
    / "ingresos"
    / "verificacion_api_indicadores_juventud.json"
)
USER_AGENT = "reto-vivienda/1.0 (proyecto educativo)"
VARIABLE_INPUT = re.compile(
    r'<input[^>]*name=["\']chkVariable_[^"\']*["\'][^>]*'
    r'value=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
PERIOD_INPUT = re.compile(
    r'<input[^>]*name=["\']chkPeriodo["\'][^>]*'
    r'value=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

INDICATORS: dict[int, dict[str, Any]] = {
    31: {
        "indicator_id": 7836,
        "classification_id": 295,
        "filename": "indicador_31_salario_portal_ovj.json",
        "expected": {
            2024: {
                "Total": Decimal("1564"),
                "Hombres": Decimal("1617"),
                "Mujeres": Decimal("1438"),
                "Álava": Decimal("1487"),
                "Bizkaia": Decimal("1585"),
                "Gipuzkoa": Decimal("1555"),
                "18-29 años": Decimal("1381"),
                "30-34 años": Decimal("1774"),
            }
        },
    },
    32: {
        "indicator_id": 8443,
        "classification_id": 295,
        "filename": "indicador_32_renta_personal_portal_ovj.json",
        "expected": {
            2023: {
                "Total": Decimal("17930"),
                "Hombres": Decimal("19076"),
                "Mujeres": Decimal("16734"),
            }
        },
    },
    49: {
        "indicator_id": 7980,
        "classification_id": 255,
        "filename": "indicador_49_acceso_alquiler_portal_ovj.json",
        "expected": {
            2024: {
                "Total": Decimal("52.4"),
                "Hombres": Decimal("50.7"),
                "Mujeres": Decimal("57"),
                "18-24 años": Decimal("69.4"),
                "25-29 años": Decimal("53.5"),
                "30-34 años": Decimal("46.2"),
                "Álava": Decimal("50.2"),
                "Bizkaia": Decimal("51.4"),
                "Gipuzkoa": Decimal("54.9"),
            }
        },
    },
}


def parse_filter_ids(html: str) -> tuple[list[str], list[str]]:
    variable_ids = VARIABLE_INPUT.findall(html)
    period_ids = PERIOD_INPUT.findall(html)
    if not variable_ids or not period_ids:
        raise ValueError("La ficha del Observatorio no contiene filtros de tabla.")
    if len(variable_ids) != len(set(variable_ids)):
        raise ValueError("La ficha del Observatorio contiene filtros duplicados.")
    if len(period_ids) != len(set(period_ids)):
        raise ValueError("La ficha del Observatorio contiene periodos duplicados.")
    return variable_ids, period_ids


def _parse_api_number(value: Any) -> Decimal:
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"Valor numérico no reconocido en la respuesta: {value!r}")
    text = str(value).strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", text):
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError(f"Valor numérico no reconocido en la respuesta: {value!r}") from error


def _labels_by_value_id(payload: dict[str, Any]) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = {}
    for section_name in ("mapaColumnas", "mapaFilas"):
        section = payload.get(section_name, {})
        if not isinstance(section, dict):
            raise ValueError(f"{section_name} no tiene el formato esperado.")
        for dimension in section.values():
            if not isinstance(dimension, dict):
                raise ValueError(f"Una dimensión de {section_name} no es válida.")
            for value_key, label in dimension.items():
                value_id = str(value_key).rsplit("_", 1)[-1]
                labels.setdefault(value_id, set()).add(str(label))
    return labels


def validate_indicator_response(
    indicator_code: int, payload: dict[str, Any]
) -> dict[str, dict[str, str]]:
    if indicator_code not in INDICATORS:
        raise ValueError(f"Indicador no configurado: {indicator_code}")
    years = payload.get("mapaAnios")
    data = payload.get("mapaDatos")
    if not isinstance(years, dict) or not isinstance(data, dict) or not data:
        raise ValueError("La respuesta JSON no contiene años y datos tabulares.")

    labels = _labels_by_value_id(payload)
    expected_by_year = INDICATORS[indicator_code]["expected"]
    verified: dict[str, dict[str, str]] = {}
    for year, expected_values in expected_by_year.items():
        matching_periods = {
            str(period_id)
            for period_id, period_year in years.items()
            if str(period_year) == str(year)
        }
        if not matching_periods:
            raise ValueError(
                f"El indicador {indicator_code} no publica el año {year}."
            )
        observed: dict[str, list[Decimal]] = {}
        for data_key, raw_value in data.items():
            components = str(data_key).split("#")
            if components[0] not in matching_periods:
                continue
            for value_id in components[1:]:
                for label in labels.get(value_id, set()):
                    if label in expected_values:
                        observed.setdefault(label, []).append(
                            _parse_api_number(raw_value)
                        )

        verified_values: dict[str, str] = {}
        for label, expected_value in expected_values.items():
            values = observed.get(label, [])
            if len(values) != 1:
                raise ValueError(
                    f"El indicador {indicator_code} {year} debe contener "
                    f"un único valor para «{label}»; se encontraron {len(values)}."
                )
            if values[0] != expected_value:
                raise ValueError(
                    f"El indicador {indicator_code} {year} no coincide con "
                    f"el valor publicado para «{label}»: {values[0]}."
                )
            verified_values[label] = format(values[0], "f")
        verified[str(year)] = verified_values
    return verified


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(content)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _read_cached(
    destination: Path, metadata_path: Path, indicator_code: int
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    if not metadata_path.is_file():
        raise FileExistsError(
            f"Existe {destination}, pero faltan sus metadatos; "
            "revise el archivo o vuelva a ejecutar con --force."
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    content = destination.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata.get("sha256"):
        raise ValueError(
            f"El hash de {destination} no coincide con sus metadatos; "
            "revise el archivo o vuelva a ejecutar con --force."
        )
    payload = json.loads(content)
    verified = validate_indicator_response(indicator_code, payload)
    return metadata, verified


def download_indicator(
    session: requests.Session, indicator_code: int, force: bool = False
) -> tuple[dict[str, Any], dict[str, dict[str, str]], bool]:
    config = INDICATORS[indicator_code]
    destination = ORIGINALS / config["filename"]
    metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")
    if destination.exists() and not force:
        metadata, verified = _read_cached(destination, metadata_path, indicator_code)
        logging.getLogger("reto_vivienda.extraccion").info(
            "Respuesta API omitida; archivo original validado: %s", destination
        )
        return metadata, verified, True

    preview_url = (
        f"{PORTAL_URL}/indicadornum/previsualizar/"
        f"{config['indicator_id']}?clid={config['classification_id']}&locale=es"
    )
    preview_response = session.get(preview_url, timeout=(15, 60))
    preview_response.raise_for_status()
    if "text/html" not in preview_response.headers.get("Content-Type", ""):
        raise ValueError(f"La ficha del indicador {indicator_code} no devolvió HTML.")
    variable_ids, period_ids = parse_filter_ids(preview_response.text)
    request_payload = {
        "FiltrarDatos": {
            "inid": config["indicator_id"],
            "variable": variable_ids,
            "periodo": period_ids,
        }
    }

    response = session.post(
        API_URL,
        json=request_payload,
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        timeout=(15, 60),
    )
    response.raise_for_status()
    if "json" not in response.headers.get("Content-Type", "").casefold():
        raise ValueError(
            f"El indicador {indicator_code} no devolvió una respuesta JSON."
        )
    payload = response.json()
    verified = validate_indicator_response(indicator_code, payload)
    content = response.content
    if not content:
        raise ValueError(f"La respuesta del indicador {indicator_code} está vacía.")

    metadata = {
        "source": "Observatorio Vasco de la Juventud",
        "dataset": "Indicadores de juventud, tabla estadística interactiva",
        "indicator_code": indicator_code,
        "indicator_id": config["indicator_id"],
        "classification_id": config["classification_id"],
        "preview_url": preview_url,
        "url": API_URL,
        "method": "POST",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "content_length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "request_payload": request_payload,
        "file": str(destination.relative_to(ROOT)),
    }
    _atomic_write(destination, content)
    _atomic_write(
        metadata_path,
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    logging.getLogger("reto_vivienda.extraccion").info(
        "Indicador %s descargado y validado mediante JSON: %s",
        indicator_code,
        destination,
    )
    return metadata, verified, False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga y verifica las tablas JSON del portal oficial de juventud."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vuelve a consultar los indicadores aunque los originales sean válidos.",
    )
    args = parser.parse_args()
    logger = configurar_logging()
    report: dict[str, Any] = {
        "status": "verified",
        "source": "Observatorio Vasco de la Juventud",
        "verification_method": "Public JSON endpoint used by the official indicator portal",
        "indicators": {},
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        for indicator_code in INDICATORS:
            metadata, verified, cached = download_indicator(
                session, indicator_code, force=args.force
            )
            report["indicators"][str(indicator_code)] = {
                "file": metadata["file"],
                "sha256": metadata["sha256"],
                "http_status": metadata["http_status"],
                "cached": cached,
                "verified_values": verified,
            }

    _atomic_write(
        REPORT_PATH,
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    logger.info(
        "Verificación del portal de juventud completada para %s indicadores.",
        len(INDICATORS),
    )
    print(
        f"API del Observatorio verificada: {len(INDICATORS)} indicadores; "
        f"evidencia en {REPORT_PATH.relative_to(ROOT)}."
    )


if __name__ == "__main__":
    main()
