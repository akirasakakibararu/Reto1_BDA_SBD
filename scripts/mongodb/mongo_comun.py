import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[2]
RAW_FILES = {
    "rent": ROOT
    / "datos"
    / "originales"
    / "alquiler"
    / "emal_alquiler_municipios_2016-2026T1.xlsx",
    "income": ROOT
    / "datos"
    / "originales"
    / "ingresos"
    / "udalmap_renta_personal_disponible.csv",
    "population": ROOT
    / "datos"
    / "originales"
    / "poblacion"
    / "udalmap_poblacion_total.csv",
}


def connection_settings() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017").strip()
    database_name = os.getenv("MONGODB_DATABASE", "reto_vivienda").strip()
    if not uri or not database_name:
        raise ValueError("MONGODB_URI y MONGODB_DATABASE no pueden estar vacíos.")
    return uri, database_name


@contextmanager
def mongo_connection() -> Generator[tuple[MongoClient, Any], None, None]:
    uri, database_name = connection_settings()
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        yield client, client[database_name]


def verified_source_metadata() -> tuple[str, dict[str, dict[str, Any]]]:
    metadata_by_source: dict[str, dict[str, Any]] = {}
    for source_name, raw_path in RAW_FILES.items():
        metadata_path = raw_path.with_suffix(raw_path.suffix + ".metadata.json")
        if not raw_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(
                f"Falta el original o su metadato de descarga: {raw_path}"
            )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if digest != metadata.get("sha256"):
            raise ValueError(f"El original no coincide con su SHA-256: {raw_path}")
        if metadata.get("http_status") != 200:
            raise ValueError(f"Descarga no verificada para {raw_path}: HTTP distinto de 200.")
        metadata_by_source[source_name] = metadata

    batch_id = hashlib.sha256(
        "|".join(
            metadata_by_source[name]["sha256"]
            for name in sorted(metadata_by_source)
        ).encode("ascii")
    ).hexdigest()
    return batch_id, metadata_by_source
