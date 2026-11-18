import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "logs" / "extraccion.log"


def configurar_logging() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
        ],
    )
    return logging.getLogger("reto_vivienda.extraccion")


def descargar_archivo(
    url: str,
    destino: Path,
    fuente: dict[str, str],
    forzar: bool = False,
) -> dict[str, Any]:
    logger = logging.getLogger("reto_vivienda.extraccion")
    destino.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = destino.with_suffix(destino.suffix + ".metadata.json")

    if destino.exists() and not forzar:
        if not metadata_path.exists():
            raise FileExistsError(
                f"Existe {destino}, pero faltan sus metadatos. "
                "Revise el archivo y vuelva a ejecutar con --force si desea descargarlo de nuevo."
            )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(destino.read_bytes()).hexdigest()
        if digest != metadata.get("sha256"):
            raise ValueError(
                f"El hash de {destino} no coincide con sus metadatos; "
                "revise el archivo y vuelva a ejecutar con --force."
            )
        logger.info("Descarga omitida; archivo local validado: %s", destino)
        return metadata

    temporary_path: str | None = None
    temporary_metadata_path: Path | None = None
    response: requests.Response | None = None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "reto-vivienda/1.0 (proyecto educativo)"},
            timeout=(15, 120),
            stream=True,
        )
        response.raise_for_status()
        digest = hashlib.sha256()
        byte_count = 0
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=destino.parent, delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    temporary_file.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)

        if byte_count == 0:
            raise ValueError(f"La respuesta de {url} no contiene datos.")
        expected_length = response.headers.get("Content-Length")
        if expected_length and int(expected_length) != byte_count:
            raise ValueError(
                f"Descarga incompleta de {url}: se esperaban {expected_length} bytes "
                f"y se recibieron {byte_count}."
            )

        os.replace(temporary_path, destino)
        temporary_path = None
        metadata = {
            **fuente,
            "url": url,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "content_length": byte_count,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "sha256": digest.hexdigest(),
            "file": str(destino.relative_to(ROOT)),
        }
        temporary_metadata_path = metadata_path.with_suffix(
            metadata_path.suffix + ".tmp"
        )
        temporary_metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_metadata_path, metadata_path)
        temporary_metadata_path = None
        logger.info(
            "Descarga completada: %s (%s bytes, SHA-256 %s)",
            destino,
            byte_count,
            metadata["sha256"],
        )
        return metadata
    except requests.RequestException:
        logger.exception("Error HTTP al descargar %s", url)
        raise
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        if temporary_metadata_path and temporary_metadata_path.exists():
            temporary_metadata_path.unlink()
        if response is not None:
            response.close()
