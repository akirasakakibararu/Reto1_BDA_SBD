import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .mongo_comun import ROOT, mongo_connection


REPORT_PATH = ROOT / "resultados" / "tablas" / "resultado_crud.json"


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    collection_name = f"crud_verificacion_{uuid.uuid4().hex}"
    report: dict[str, Any] | None = None
    with mongo_connection() as (_, database):
        database.create_collection(collection_name)
        collection = database[collection_name]
        try:
            document = {
                "_id": f"crud-{uuid.uuid4().hex}",
                "municipality_code": "TEST",
                "status": "created",
            }
            create_result = collection.insert_one(document)
            if not create_result.acknowledged:
                raise RuntimeError("MongoDB no confirmó la operación Create.")

            read_document = collection.find_one({"_id": create_result.inserted_id})
            if read_document != document:
                raise RuntimeError("La lectura Read no devolvió el documento insertado.")

            update_result = collection.update_one(
                {"_id": create_result.inserted_id},
                {"$set": {"status": "updated", "verified": True}},
            )
            updated_document = collection.find_one({"_id": create_result.inserted_id})
            if (
                update_result.modified_count != 1
                or updated_document is None
                or updated_document.get("status") != "updated"
                or updated_document.get("verified") is not True
            ):
                raise RuntimeError("La operación Update no se verificó.")

            delete_result = collection.delete_one({"_id": create_result.inserted_id})
            remaining_document = collection.find_one(
                {"_id": create_result.inserted_id}
            )
            if delete_result.deleted_count != 1 or remaining_document is not None:
                raise RuntimeError("La operación Delete no se verificó.")

            report = {
                "status": "verified",
                "database": database.name,
                "temporary_collection": collection_name,
                "create": {
                    "acknowledged": create_result.acknowledged,
                    "inserted_id": str(create_result.inserted_id),
                },
                "read": {"document_found": read_document is not None},
                "update": {
                    "matched_count": update_result.matched_count,
                    "modified_count": update_result.modified_count,
                    "updated_value": updated_document["status"],
                },
                "delete": {
                    "deleted_count": delete_result.deleted_count,
                    "document_absent_after_delete": remaining_document is None,
                },
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            database.drop_collection(collection_name)
        if collection_name in database.list_collection_names():
            raise RuntimeError("No se pudo retirar la colección CRUD temporal.")
    if report is None:
        raise RuntimeError("No se generó el resultado de la comprobación CRUD.")
    report["temporary_collection_removed"] = True
    _write_report(report)


if __name__ == "__main__":
    main()
