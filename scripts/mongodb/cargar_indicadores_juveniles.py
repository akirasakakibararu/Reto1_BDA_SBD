import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128
from pymongo import ReplaceOne

from scripts.extraccion.descarga_comun import ROOT
from scripts.mongodb.mongo_comun import mongo_connection


PROCESSED = ROOT / "datos" / "procesados" / "ingresos"
PDF_PATH = (
    ROOT
    / "datos"
    / "originales"
    / "juventud"
    / "indicadores_de_juventud_2025.pdf"
)
PDF_METADATA_PATH = PDF_PATH.with_suffix(PDF_PATH.suffix + ".metadata.json")
SALARY_PATH = PROCESSED / "salarios_juveniles_observatorio.csv"
REFERENCE_PATH = PROCESSED / "referencias_juveniles_observatorio.csv"
REPORT_PATH = ROOT / "resultados" / "tablas" / "carga_indicadores_juveniles.json"
EXPECTED_TERRITORY_CODES = {"01", "20", "48"}
REFERENCE_METRICS = {
    32: "personal_income_annual",
    49: "rent_access_percent",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"No existe el dato procesado o está vacío: {path}")
    with path.open(encoding="utf-8-sig", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    if not rows:
        raise ValueError(f"El fichero procesado no contiene registros: {path}")
    return rows


def _verified_pdf_metadata() -> dict[str, Any]:
    if not PDF_PATH.is_file() or not PDF_METADATA_PATH.is_file():
        raise FileNotFoundError(
            "Falta el PDF oficial de juventud o su archivo de metadatos."
        )
    metadata = json.loads(PDF_METADATA_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    if digest != metadata.get("sha256") or metadata.get("http_status") != 200:
        raise ValueError("El PDF de juventud no supera la verificación de origen.")
    if metadata.get("url") != (
        "https://www.gazteaukera.euskadi.eus/contenidos/noticia/"
        "txostena_panorama_2025/es_def/adjuntos/Indicadores-de-Juventud-2025.pdf"
    ):
        raise ValueError("La procedencia del PDF de juventud no es la esperada.")
    return metadata


def _source(
    metadata: dict[str, Any], row: dict[str, str], indicator_code: int
) -> dict[str, Any]:
    source_name = (
        "Eustat (Estadística de renta personal y familiar)"
        if indicator_code == 32
        else "Observatorio Vasco de la Juventud"
    )
    return {
        "name": source_name,
        "publication": "Indicadores de Juventud 2025",
        "url": metadata["url"],
        "file": metadata["file"],
        "sha256": metadata["sha256"],
        "batch_id": metadata["sha256"],
        "downloaded_at_utc": metadata["downloaded_at_utc"],
        "indicator_code": indicator_code,
        "source_page": int(row["source_page"]),
    }


def _dimension_id(row: dict[str, str]) -> str:
    territory_code = row["territory_code"] or "none"
    return ":".join(
        (
            row["indicator_code"],
            row["year"],
            row["geography_level"],
            territory_code,
            row["age_group"],
            row["sex"],
        )
    )


def build_salary_documents(
    rows: list[dict[str, str]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    documents = []
    for row in rows:
        territory_code = row["territory_code"] or None
        if row["geography_level"] == "territory" and territory_code not in (
            EXPECTED_TERRITORY_CODES
        ):
            raise ValueError(f"Código territorial inesperado: {territory_code}")
        documents.append(
            {
                "_id": _dimension_id(row),
                "indicator_code": int(row["indicator_code"]),
                "year": int(row["year"]),
                "geography_level": row["geography_level"],
                "territory_code": territory_code,
                "territory_name": row["territory_name"],
                "age_group": row["age_group"],
                "sex": row["sex"],
                "net_monthly_salary_eur": Decimal128(
                    Decimal(row["net_monthly_salary_eur"])
                ),
                "unit": row["unit"],
                "salary_definition": (
                    "Net monthly mean salary of salaried people aged 18-34; "
                    "extra payments prorated."
                ),
                "source": _source(metadata, row, 31),
            }
        )
    _assert_unique_documents(documents, "salarios juveniles")
    territory_codes = {
        document["territory_code"]
        for document in documents
        if document["geography_level"] == "territory"
    }
    if territory_codes != EXPECTED_TERRITORY_CODES:
        raise ValueError(
            f"Códigos territoriales extraídos inesperados: {territory_codes}"
        )
    return documents


def build_reference_documents(
    rows: list[dict[str, str]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    documents = []
    for row in rows:
        indicator_code = int(row["indicator_code"])
        if REFERENCE_METRICS.get(indicator_code) != row["metric"]:
            raise ValueError(
                f"Métrica inesperada para el indicador {indicator_code}: "
                f"{row['metric']}."
            )
        territory_code = row["territory_code"] or None
        if row["geography_level"] == "territory" and territory_code not in (
            EXPECTED_TERRITORY_CODES
        ):
            raise ValueError(f"Código territorial inesperado: {territory_code}")
        documents.append(
            {
                "_id": _dimension_id(row),
                "indicator_code": indicator_code,
                "year": int(row["year"]),
                "geography_level": row["geography_level"],
                "territory_code": territory_code,
                "territory_name": row["territory_name"],
                "age_group": row["age_group"],
                "sex": row["sex"],
                "metric": row["metric"],
                "value": Decimal128(Decimal(row["value"])),
                "unit": row["unit"],
                "definition": (
                    "Annual mean personal income, not salary."
                    if indicator_code == 32
                    else "Share of net monthly salary needed to pay rent alone."
                ),
                "source": _source(metadata, row, indicator_code),
            }
        )
    _assert_unique_documents(documents, "referencias juveniles")
    return documents


def _assert_unique_documents(
    documents: list[dict[str, Any]], label: str
) -> None:
    identifiers = [document["_id"] for document in documents]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"Hay documentos duplicados en {label}.")


def _upsert_documents(collection: Any, documents: list[dict[str, Any]]) -> dict[str, int]:
    if not documents:
        raise ValueError(f"No se cargará una colección vacía: {collection.name}")
    result = collection.bulk_write(
        [
            ReplaceOne({"_id": document["_id"]}, document, upsert=True)
            for document in documents
        ],
        ordered=False,
    )
    return {
        "upserted": result.upserted_count,
        "modified": result.modified_count,
        "matched": result.matched_count,
    }


def _duplicate_groups(collection: Any) -> int:
    result = list(
        collection.aggregate(
            [
                {
                    "$group": {
                        "_id": {
                            "indicator_code": "$indicator_code",
                            "year": "$year",
                            "geography_level": "$geography_level",
                            "territory_code": "$territory_code",
                            "age_group": "$age_group",
                            "sex": "$sex",
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$match": {"count": {"$gt": 1}}},
                {"$count": "duplicate_groups"},
            ]
        )
    )
    return int(result[0]["duplicate_groups"]) if result else 0


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                ROOT / "logs" / "mongodb.log",
                encoding="utf-8",
            ),
        ],
    )
    logger = logging.getLogger("reto_vivienda.mongodb.juventud")
    source_metadata = _verified_pdf_metadata()
    salary_documents = build_salary_documents(
        _read_csv(SALARY_PATH), source_metadata
    )
    reference_documents = build_reference_documents(
        _read_csv(REFERENCE_PATH), source_metadata
    )

    with mongo_connection() as (client, database):
        salaries = database["salarios_juveniles"]
        references = database["referencias_juventud"]
        salaries.create_index(
            [
                ("indicator_code", 1),
                ("year", 1),
                ("geography_level", 1),
                ("territory_code", 1),
                ("age_group", 1),
                ("sex", 1),
            ],
            unique=True,
            name="uq_salario_indicador_geografia_periodo",
        )
        references.create_index(
            [
                ("indicator_code", 1),
                ("year", 1),
                ("geography_level", 1),
                ("territory_code", 1),
                ("age_group", 1),
                ("sex", 1),
            ],
            unique=True,
            name="uq_referencia_indicador_geografia_periodo",
        )
        results = {
            "salarios_juveniles": _upsert_documents(salaries, salary_documents),
            "referencias_juventud": _upsert_documents(
                references, reference_documents
            ),
        }
        batch_id = source_metadata["sha256"]
        pruned = {
            collection.name: collection.delete_many(
                {
                    "source.publication": "Indicadores de Juventud 2025",
                    "source.batch_id": {"$ne": batch_id},
                }
            ).deleted_count
            for collection in (salaries, references)
        }
        counts = {
            "salarios_juveniles": salaries.count_documents(
                {"source.batch_id": batch_id}
            ),
            "referencias_juventud": references.count_documents(
                {"source.batch_id": batch_id}
            ),
        }
        expected = {
            "salarios_juveniles": len(salary_documents),
            "referencias_juventud": len(reference_documents),
        }
        if counts != expected:
            raise RuntimeError(
                f"Conteos de carga inesperados: esperados={expected}, obtenidos={counts}"
            )
        duplicates = {
            collection.name: _duplicate_groups(collection)
            for collection in (salaries, references)
        }
        if any(duplicates.values()):
            raise RuntimeError(f"Se detectaron dimensiones duplicadas: {duplicates}")
        non_decimal = {
            "salarios_juveniles": salaries.count_documents(
                {"net_monthly_salary_eur": {"$not": {"$type": "decimal"}}}
            ),
            "referencias_juventud": references.count_documents(
                {"value": {"$not": {"$type": "decimal"}}}
            ),
        }
        if any(non_decimal.values()):
            raise RuntimeError(
                f"Se detectaron valores monetarios no Decimal128: {non_decimal}"
            )
        report = {
            "status": "verified",
            "database": database.name,
            "mongodb_server_version": client.server_info()["version"],
            "source_sha256": batch_id,
            "documents_expected": expected,
            "documents_by_collection": counts,
            "bulk_write": results,
            "duplicate_groups": duplicates,
            "non_decimal_measurements": non_decimal,
            "previous_source_documents_pruned": pruned,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_report(report)
    logger.info(
        "Carga de indicadores juveniles verificada: salarios=%s, referencias=%s.",
        counts["salarios_juveniles"],
        counts["referencias_juventud"],
    )


if __name__ == "__main__":
    main()
