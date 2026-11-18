import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128
from pymongo.collection import Collection

from .mongo_comun import ROOT, mongo_connection


TABLES_PATH = ROOT / "resultados" / "tablas"
RENT_INDEX = "ix_alquiler_anio_geografia_renta"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stage_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        stage = value.get("stage")
        if isinstance(stage, str):
            names.append(stage)
        for nested in value.values():
            names.extend(_stage_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.extend(_stage_names(nested))
    return names


def _explain_summary(
    collection: Collection, query: dict[str, Any], hint: str | dict[str, int]
) -> dict[str, Any]:
    explanation = collection.database.command(
        "explain",
        {
            "find": collection.name,
            "filter": query,
            "hint": hint,
        },
        verbosity="executionStats",
    )
    winning_plan = explanation["queryPlanner"]["winningPlan"]
    execution = explanation["executionStats"]
    return {
        "hint": hint,
        "winning_plan_stages": _stage_names(winning_plan),
        "total_docs_examined": execution["totalDocsExamined"],
        "total_keys_examined": execution["totalKeysExamined"],
        "n_returned": execution["nReturned"],
        "winning_plan": winning_plan,
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "logs" / "mongodb.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("reto_vivienda.mongodb")
    query = {
        "year": 2023,
        "geography.included_in_current_boundary_comparison": True,
        "rental.monthly_eur": {"$lt": Decimal128("600")},
    }
    with mongo_connection() as (_, database):
        rentals = database["alquileres"]
        before_index = _explain_summary(rentals, query, {"$natural": 1})
        index_name = rentals.create_index(
            [
                ("year", 1),
                ("geography.included_in_current_boundary_comparison", 1),
                ("rental.monthly_eur", 1),
            ],
            name=RENT_INDEX,
        )
        after_index = _explain_summary(rentals, query, RENT_INDEX)
        if "COLLSCAN" not in before_index["winning_plan_stages"]:
            raise RuntimeError("La explicación sin índice no mostró COLLSCAN.")
        if "IXSCAN" not in after_index["winning_plan_stages"]:
            raise RuntimeError("La explicación con índice no mostró IXSCAN.")

        database["socioeconomicos"].create_index(
            [("year", 1), ("indicators.available_income_eur", -1)],
            name="ix_socio_anio_renta_disponible",
        )
        database["municipios"].create_index(
            [("territory.code", 1), ("municipality_name", 1)],
            name="ix_municipios_territorio_nombre",
        )

        counter = database["operaciones_atomicas"]
        before = counter.find_one({"_id": "demostraciones_update_one"})
        previous_count = before.get("atomic_update_count", 0) if before else 0
        update_result = counter.update_one(
            {"_id": "demostraciones_update_one"},
            {
                "$inc": {"atomic_update_count": 1},
                "$set": {
                    "description": (
                        "Contador de ejecuciones de la demostración atómica; "
                        "no es un indicador socioeconómico."
                    )
                },
                "$setOnInsert": {
                    "created_at_utc": datetime.now(timezone.utc).isoformat()
                },
            },
            upsert=True,
        )
        after = counter.find_one({"_id": "demostraciones_update_one"})
        if after is None or after.get("atomic_update_count") != previous_count + 1:
            raise RuntimeError("No se verificó el incremento atómico con $inc.")

        index_report = {
            "status": "verified",
            "database": database.name,
            "query": query,
            "index_created": index_name,
            "natural_scan": before_index,
            "with_index": after_index,
            "index_information": {
                collection.name: collection.index_information()
                for collection in (
                    database["alquileres"],
                    database["socioeconomicos"],
                    database["municipios"],
                )
            },
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        atomic_report = {
            "status": "verified",
            "database": database.name,
            "collection": counter.name,
            "operation": "update_one with $inc and upsert",
            "atomic_update_count_before": previous_count,
            "atomic_update_count_after": after["atomic_update_count"],
            "matched_count": update_result.matched_count,
            "modified_count": update_result.modified_count,
            "upserted_id": (
                str(update_result.upserted_id)
                if update_result.upserted_id is not None
                else None
            ),
            "transaction_required": False,
            "transaction_reason": (
                "Each source observation is an independently keyed record. "
                "The ETL uses deterministic upserts and verifies the full batch; "
                "there is no business invariant requiring a multi-document transaction. "
                "A single-document $inc is atomic."
            ),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    _write_json(TABLES_PATH / "explain_indices.json", index_report)
    _write_json(TABLES_PATH / "operacion_atomica.json", atomic_report)
    logger.info("Índices, explain y operación atómica verificados.")


if __name__ == "__main__":
    main()
