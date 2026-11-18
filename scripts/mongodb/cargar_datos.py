import csv
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128
from pymongo import ReplaceOne

from .mongo_comun import ROOT, mongo_connection, verified_source_metadata


PROCESSED = ROOT / "datos" / "procesados"
REPORT_PATH = ROOT / "resultados" / "tablas" / "resultado_carga_mongodb.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"No existe el dato procesado o está vacío: {path}")
    with path.open(encoding="utf-8-sig", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    if not rows:
        raise ValueError(f"El fichero procesado no contiene registros: {path}")
    return rows


def _decimal128(value: str) -> Decimal128 | None:
    if value == "":
        return None
    return Decimal128(Decimal(value))


def _read_boolean(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Valor booleano no válido en CSV: {value!r}")


def _source_file_metadata(
    source_name: str,
    batch_id: str,
    metadata: dict[str, Any],
    *,
    row: str | None = None,
    sheets: list[str] | None = None,
) -> dict[str, Any]:
    source = {
        "kind": source_name,
        "name": metadata["source"],
        "url": metadata["url"],
        "file": metadata["file"],
        "sha256": metadata["sha256"],
        "batch_id": batch_id,
        "downloaded_at_utc": metadata["downloaded_at_utc"],
    }
    if row is not None:
        source["source_row"] = int(row)
    if sheets is not None:
        source["sheets"] = sheets
    return source


def _build_municipality_documents(
    rows: list[dict[str, str]], batch_id: str, population_metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "_id": row["municipality_code"],
            "municipality_code": row["municipality_code"],
            "municipality_name": row["municipality_name"],
            "territory": {
                "code": row["territory_code"],
                "name": row["territory_name"],
            },
            "source": _source_file_metadata(
                "population", batch_id, population_metadata
            ),
        }
        for row in rows
    ]


def _build_rental_documents(
    rows: list[dict[str, str]], batch_id: str, rent_metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    documents = []
    for row in rows:
        variant = row["geography_variant"]
        municipality_code = row["municipality_code"]
        year = int(row["year"])
        documents.append(
            {
                "_id": f"{municipality_code}:{variant}:{year}",
                "municipality_code": municipality_code,
                "municipality_name": row["municipality_name"],
                "municipality_name_source": row["municipality_name_source"],
                "year": year,
                "geography": {
                    "variant": variant,
                    "included_in_current_boundary_comparison": _read_boolean(
                        row["included_in_current_boundary_comparison"]
                    ),
                },
                "rental": {
                    "monthly_eur": _decimal128(row["monthly_rent_eur"]),
                    "per_m2_eur": _decimal128(row["rent_per_m2_eur"]),
                    "deposit_count": (
                        int(row["deposit_count"]) if row["deposit_count"] else None
                    ),
                },
                "reference": {
                    "rent_reference": row["rent_reference"],
                    "historical_adjustment_note": row[
                        "historical_rent_adjustment_note"
                    ],
                },
                "source": _source_file_metadata(
                    "rent",
                    batch_id,
                    rent_metadata,
                    sheets=row["source_sheets"].split(";"),
                ),
                "source_row_by_sheet": {
                    "T2.1": int(row["source_row_T2.1"]),
                    "T2.2": int(row["source_row_T2.2"]),
                    "T2.3": int(row["source_row_T2.3"]),
                },
            }
        )
    return documents


def _build_socioeconomic_documents(
    income_rows: list[dict[str, str]],
    population_rows: list[dict[str, str]],
    batch_id: str,
    income_metadata: dict[str, Any],
    population_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for row in population_rows:
        code = row["municipality_code"]
        year = int(row["year"])
        document = merged.setdefault(
            (code, year),
            {
                "_id": f"{code}:{year}",
                "municipality_code": code,
                "municipality_name": row["municipality_name"],
                "year": year,
                "indicators": {},
                "source": {"batch_id": batch_id},
            },
        )
        if document["municipality_name"] != row["municipality_name"]:
            raise ValueError(f"Nombre inconsistente por año para {code}.")
        document["indicators"]["population"] = (
            int(row["population"]) if row["population"] else None
        )
        document["source"]["population"] = _source_file_metadata(
            "population",
            batch_id,
            population_metadata,
            row=row["source_row"],
        )

    for row in income_rows:
        code = row["municipality_code"]
        year = int(row["year"])
        document = merged.setdefault(
            (code, year),
            {
                "_id": f"{code}:{year}",
                "municipality_code": code,
                "municipality_name": row["municipality_name"],
                "year": year,
                "indicators": {},
                "source": {"batch_id": batch_id},
            },
        )
        if document["municipality_name"] != row["municipality_name"]:
            raise ValueError(f"Nombre inconsistente entre fuentes para {code}.")
        document["indicators"]["available_income_eur"] = _decimal128(
            row["available_income_eur"]
        )
        document["source"]["available_income"] = _source_file_metadata(
            "income",
            batch_id,
            income_metadata,
            row=row["source_row"],
        )
    return sorted(merged.values(), key=lambda document: document["_id"])


def _upsert_documents(collection: Any, documents: list[dict[str, Any]]) -> dict[str, int]:
    if not documents:
        raise ValueError(f"No se cargará una colección vacía: {collection.name}")
    operations = [
        ReplaceOne({"_id": document["_id"]}, document, upsert=True)
        for document in documents
    ]
    result = collection.bulk_write(operations, ordered=False)
    return {
        "upserted": result.upserted_count,
        "modified": result.modified_count,
        "matched": result.matched_count,
    }


def _duplicate_group_count(
    collection: Any, grouped_fields: dict[str, str]
) -> int:
    duplicates = list(
        collection.aggregate(
            [
                {"$group": {"_id": grouped_fields, "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}},
                {"$count": "duplicate_groups"},
            ]
        )
    )
    return int(duplicates[0]["duplicate_groups"]) if duplicates else 0


def _clean_and_transform(
    rentals: Any, socioeconomic: Any
) -> dict[str, Any]:
    nulls_rent = rentals.update_many(
        {},
        [
            {
                "$set": {
                    "rental.monthly_eur": {
                        "$ifNull": ["$rental.monthly_eur", None]
                    },
                    "rental.per_m2_eur": {
                        "$ifNull": ["$rental.per_m2_eur", None]
                    },
                    "rental.deposit_count": {
                        "$ifNull": ["$rental.deposit_count", None]
                    },
                }
            }
        ],
    )
    nulls_socioeconomic = socioeconomic.update_many(
        {},
        [
            {
                "$set": {
                    "indicators.available_income_eur": {
                        "$ifNull": [
                            "$indicators.available_income_eur",
                            None,
                        ]
                    },
                    "indicators.population": {
                        "$ifNull": ["$indicators.population", None]
                    },
                }
            }
        ],
    )

    types_rent = rentals.update_many(
        {},
        [
            {
                "$set": {
                    "rental.monthly_eur": {
                        "$convert": {
                            "input": "$rental.monthly_eur",
                            "to": "decimal",
                            "onNull": None,
                        }
                    },
                    "rental.per_m2_eur": {
                        "$convert": {
                            "input": "$rental.per_m2_eur",
                            "to": "decimal",
                            "onNull": None,
                        }
                    },
                    "rental.deposit_count": {
                        "$convert": {
                            "input": "$rental.deposit_count",
                            "to": "int",
                            "onNull": None,
                        }
                    },
                }
            }
        ],
    )
    types_socioeconomic = socioeconomic.update_many(
        {},
        [
            {
                "$set": {
                    "indicators.available_income_eur": {
                        "$convert": {
                            "input": "$indicators.available_income_eur",
                            "to": "decimal",
                            "onNull": None,
                        }
                    },
                    "indicators.population": {
                        "$convert": {
                            "input": "$indicators.population",
                            "to": "long",
                            "onNull": None,
                        }
                    },
                }
            }
        ],
    )

    annual_rent = rentals.update_many(
        {},
        [
            {
                "$set": {
                    "rental.annual_eur": {
                        "$cond": [
                            {
                                "$eq": [
                                    {"$ifNull": ["$rental.monthly_eur", None]},
                                    None,
                                ]
                            },
                            None,
                            {
                                "$multiply": [
                                    "$rental.monthly_eur",
                                    Decimal128("12"),
                                ]
                            },
                        ]
                    }
                }
            }
        ],
    )
    monthly_income = socioeconomic.update_many(
        {},
        [
            {
                "$set": {
                    "indicators.available_income_monthly_eur": {
                        "$cond": [
                            {
                                "$eq": [
                                    {
                                        "$ifNull": [
                                            "$indicators.available_income_eur",
                                            None,
                                        ]
                                    },
                                    None,
                                ]
                            },
                            None,
                            {
                                "$divide": [
                                    "$indicators.available_income_eur",
                                    Decimal128("12"),
                                ]
                            },
                        ]
                    }
                }
            }
        ],
    )

    duplicate_groups = {
        "alquileres": _duplicate_group_count(
            rentals,
            {
                "municipality_code": "$municipality_code",
                "geography_variant": "$geography.variant",
                "year": "$year",
            },
        ),
        "socioeconomicos": _duplicate_group_count(
            socioeconomic,
            {
                "municipality_code": "$municipality_code",
                "year": "$year",
            },
        ),
    }
    if any(duplicate_groups.values()):
        raise RuntimeError(f"Se detectaron claves duplicadas: {duplicate_groups}")

    missing_derived_fields = {
        "alquileres": rentals.count_documents(
            {"rental.annual_eur": {"$exists": False}}
        ),
        "socioeconomicos": socioeconomic.count_documents(
            {"indicators.available_income_monthly_eur": {"$exists": False}}
        ),
    }
    if any(missing_derived_fields.values()):
        raise RuntimeError(
            "No se materializaron todos los campos derivados: "
            f"{missing_derived_fields}"
        )

    return {
        "null_and_absent_values": {
            "alquileres_matched": nulls_rent.matched_count,
            "alquileres_modified": nulls_rent.modified_count,
            "socioeconomicos_matched": nulls_socioeconomic.matched_count,
            "socioeconomicos_modified": nulls_socioeconomic.modified_count,
        },
        "bson_type_corrections": {
            "alquileres_matched": types_rent.matched_count,
            "alquileres_modified": types_rent.modified_count,
            "socioeconomicos_matched": types_socioeconomic.matched_count,
            "socioeconomicos_modified": types_socioeconomic.modified_count,
        },
        "duplicate_groups": duplicate_groups,
        "derived_fields": {
            "rental.annual_eur": {
                "matched": annual_rent.matched_count,
                "modified": annual_rent.modified_count,
                "missing_after_transform": missing_derived_fields["alquileres"],
                "operation": "$multiply monthly rent by 12",
            },
            "indicators.available_income_monthly_eur": {
                "matched": monthly_income.matched_count,
                "modified": monthly_income.modified_count,
                "missing_after_transform": missing_derived_fields[
                    "socioeconomicos"
                ],
                "operation": "$divide annual available income by 12",
            },
        },
    }


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
            logging.FileHandler(ROOT / "logs" / "mongodb.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("reto_vivienda.mongodb")
    batch_id, metadata = verified_source_metadata()
    municipality_rows = _read_csv(PROCESSED / "municipios_referencia.csv")
    rental_rows = _read_csv(
        PROCESSED / "alquiler" / "emal_alquiler_municipal_anual.csv"
    )
    income_rows = _read_csv(
        PROCESSED / "ingresos" / "udalmap_renta_municipal_anual.csv"
    )
    population_rows = _read_csv(
        PROCESSED / "poblacion" / "udalmap_poblacion_municipal_anual.csv"
    )

    municipality_documents = _build_municipality_documents(
        municipality_rows, batch_id, metadata["population"]
    )
    rental_documents = _build_rental_documents(
        rental_rows, batch_id, metadata["rent"]
    )
    socioeconomic_documents = _build_socioeconomic_documents(
        income_rows,
        population_rows,
        batch_id,
        metadata["income"],
        metadata["population"],
    )
    if len({document["_id"] for document in rental_documents}) != len(
        rental_documents
    ):
        raise ValueError("Hay identificadores de alquiler duplicados.")
    if len({document["_id"] for document in socioeconomic_documents}) != len(
        socioeconomic_documents
    ):
        raise ValueError("Hay identificadores socioeconómicos duplicados.")

    with mongo_connection() as (client, database):
        municipalities = database["municipios"]
        rentals = database["alquileres"]
        socioeconomic = database["socioeconomicos"]
        rentals.create_index(
            [
                ("municipality_code", 1),
                ("geography.variant", 1),
                ("year", 1),
            ],
            unique=True,
            name="uq_alquiler_municipio_geografia_anio",
        )
        socioeconomic.create_index(
            [("municipality_code", 1), ("year", 1)],
            unique=True,
            name="uq_socioeconomico_municipio_anio",
        )

        results = {
            "municipios": _upsert_documents(municipalities, municipality_documents),
            "alquileres": _upsert_documents(rentals, rental_documents),
            "socioeconomicos": _upsert_documents(
                socioeconomic, socioeconomic_documents
            ),
        }
        cleaning = _clean_and_transform(rentals, socioeconomic)
        pruned = {
            collection.name: collection.delete_many(
                {"source.batch_id": {"$exists": True, "$ne": batch_id}}
            ).deleted_count
            for collection in (municipalities, rentals, socioeconomic)
        }
        counts = {
            collection.name: collection.count_documents(
                {"source.batch_id": batch_id}
            )
            for collection in (municipalities, rentals, socioeconomic)
        }
        expected = {
            "municipios": len(municipality_documents),
            "alquileres": len(rental_documents),
            "socioeconomicos": len(socioeconomic_documents),
        }
        if counts != expected:
            raise RuntimeError(
                f"Conteos de carga inesperados: esperados={expected}, obtenidos={counts}"
            )
        report = {
            "status": "verified",
            "database": database.name,
            "mongodb_server_version": client.server_info()["version"],
            "batch_id": batch_id,
            "verified_source_sha256": {
                name: source["sha256"] for name, source in metadata.items()
            },
            "documents_expected": expected,
            "documents_by_collection": counts,
            "bulk_write": results,
            "cleaning_and_transformation": cleaning,
            "previous_source_documents_pruned": pruned,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_report(report)
    logger.info("Carga idempotente verificada: %s", REPORT_PATH)


if __name__ == "__main__":
    main()
