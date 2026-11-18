import json
import logging
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128

from .mongo_comun import ROOT, mongo_connection
from .consultas_juveniles import youth_pipeline_specs


TABLES_PATH = ROOT / "resultados" / "tablas"
YEAR = 2023
MONEY_ZERO = Decimal128("0")
TWELVE = Decimal128("12")
ONE_HUNDRED = Decimal128("100")


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _query_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "alquiler_de_donostia_2023",
            "collection": "alquileres",
            "filter": {
                "municipality_code": "20069",
                "year": YEAR,
                "geography.included_in_current_boundary_comparison": True,
            },
            "projection": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": 1,
                "year": 1,
                "rental": 1,
                "reference": 1,
            },
            "sort": [],
            "limit": 1,
        },
        {
            "name": "alquiler_mensual_inferior_a_600_euros_2023",
            "collection": "alquileres",
            "filter": {
                "year": YEAR,
                "geography.included_in_current_boundary_comparison": True,
                "rental.monthly_eur": {"$lt": Decimal128("600")},
            },
            "projection": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": 1,
                "year": 1,
                "rental.monthly_eur": 1,
            },
            "sort": [("rental.monthly_eur", 1)],
            "limit": 20,
        },
        {
            "name": "municipios_mayores_de_10000_con_renta_positiva_2023",
            "collection": "socioeconomicos",
            "filter": {
                "$and": [
                    {"year": YEAR},
                    {"indicators.population": {"$gte": 10000}},
                    {"indicators.available_income_eur": {"$gt": MONEY_ZERO}},
                ]
            },
            "projection": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": 1,
                "year": 1,
                "indicators.population": 1,
                "indicators.available_income_eur": 1,
            },
            "sort": [("indicators.available_income_eur", -1)],
            "limit": 10,
        },
        {
            "name": "alquiler_2023_con_procedencia_de_la_hoja_T2_2",
            "collection": "alquileres",
            "filter": {
                "year": YEAR,
                "geography.included_in_current_boundary_comparison": True,
                "source.sheets": "T2.2",
            },
            "projection": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": 1,
                "year": 1,
                "geography.variant": 1,
                "rental.monthly_eur": 1,
                "source.sheets": 1,
            },
            "sort": [("rental.monthly_eur", 1)],
            "limit": 10,
        },
        {
            "name": "diez_municipios_con_mayor_renta_disponible_2023",
            "collection": "socioeconomicos",
            "filter": {
                "year": YEAR,
                "indicators.available_income_eur": {"$gt": MONEY_ZERO},
            },
            "projection": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": 1,
                "year": 1,
                "indicators.available_income_eur": 1,
            },
            "sort": [("indicators.available_income_eur", -1)],
            "limit": 10,
        },
    ]


def _socioeconomic_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "socioeconomicos",
            "let": {"code": "$municipality_code", "year": "$year"},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$municipality_code", "$$code"]},
                                {"$eq": ["$year", "$$year"]},
                            ]
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "indicators.available_income_eur": 1,
                        "indicators.population": 1,
                    }
                },
            ],
            "as": "socioeconomic",
        }
    }


def _municipality_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "municipios",
            "localField": "municipality_code",
            "foreignField": "_id",
            "as": "municipality",
        }
    }


def _monthly_affordability_fields() -> dict[str, Any]:
    monthly_income = {
        "$divide": ["$socioeconomic.indicators.available_income_eur", TWELVE]
    }
    return {
        "$addFields": {
            "indicators.monthly_available_income_eur": monthly_income,
            "indicators.rent_as_share_of_available_income_percent": {
                "$multiply": [
                    {"$divide": ["$rental.monthly_eur", monthly_income]},
                    ONE_HUNDRED,
                ]
            },
            "indicators.monthly_remaining_after_rent_eur": {
                "$subtract": [monthly_income, "$rental.monthly_eur"]
            },
        }
    }


def _affordability_prefix() -> list[dict[str, Any]]:
    return [
        {
            "$match": {
                "year": YEAR,
                "geography.included_in_current_boundary_comparison": True,
                "rental.monthly_eur": {"$gt": MONEY_ZERO},
            }
        },
        _socioeconomic_lookup(),
        {"$unwind": "$socioeconomic"},
        {
            "$match": {
                "socioeconomic.indicators.available_income_eur": {
                    "$gt": MONEY_ZERO
                }
            }
        },
        _municipality_lookup(),
        {"$unwind": "$municipality"},
        _monthly_affordability_fields(),
    ]


def pipeline_specs() -> dict[str, list[dict[str, Any]]]:
    return {
        "municipios_ordenados_por_esfuerzo_de_alquiler_2023": [
            *_affordability_prefix(),
            {
                "$project": {
                    "_id": 0,
                    "municipality_code": 1,
                    "municipality_name": "$municipality.municipality_name",
                    "territory_name": "$municipality.territory.name",
                    "year": 1,
                    "population": "$socioeconomic.indicators.population",
                    "monthly_rent_eur": "$rental.monthly_eur",
                    "rent_per_m2_eur": "$rental.per_m2_eur",
                    "deposit_count": "$rental.deposit_count",
                    "available_income_annual_eur": (
                        "$socioeconomic.indicators.available_income_eur"
                    ),
                    "monthly_available_income_eur": (
                        "$indicators.monthly_available_income_eur"
                    ),
                    "rent_as_share_of_available_income_percent": (
                        "$indicators.rent_as_share_of_available_income_percent"
                    ),
                    "monthly_remaining_after_rent_eur": (
                        "$indicators.monthly_remaining_after_rent_eur"
                    ),
                    "income_measure": {
                        "$literal": (
                            "Adult mean available personal income, not a youth wage"
                        )
                    },
                }
            },
            {"$sort": {"rent_as_share_of_available_income_percent": 1}},
        ],
        "evolucion_del_alquiler_ponderada_por_fianzas_y_territorio": [
            {
                "$match": {
                    "geography.included_in_current_boundary_comparison": True,
                    "rental.monthly_eur": {"$gt": MONEY_ZERO},
                    "rental.deposit_count": {"$gt": 0},
                }
            },
            _municipality_lookup(),
            {"$unwind": "$municipality"},
            {
                "$group": {
                    "_id": {
                        "territory_code": "$municipality.territory.code",
                        "territory_name": "$municipality.territory.name",
                        "year": "$year",
                    },
                    "weighted_rent_sum": {
                        "$sum": {
                            "$multiply": [
                                "$rental.monthly_eur",
                                "$rental.deposit_count",
                            ]
                        }
                    },
                    "total_deposits": {"$sum": "$rental.deposit_count"},
                    "municipality_count": {"$sum": 1},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "territory_code": "$_id.territory_code",
                    "territory_name": "$_id.territory_name",
                    "year": "$_id.year",
                    "weighted_monthly_rent_eur": {
                        "$divide": ["$weighted_rent_sum", "$total_deposits"]
                    },
                    "total_deposits": 1,
                    "municipality_count": 1,
                }
            },
            {"$sort": {"territory_code": 1, "year": 1}},
        ],
        "resumen_de_emancipacion_por_territorio_2023": [
            *_affordability_prefix(),
            {
                "$facet": {
                    "resumen_territorial": [
                        {
                            "$group": {
                                "_id": {
                                    "territory_code": "$municipality.territory.code",
                                    "territory_name": "$municipality.territory.name",
                                },
                                "municipality_count": {"$sum": 1},
                                "average_rent_eur": {"$avg": "$rental.monthly_eur"},
                                "average_annual_available_income_eur": {
                                    "$avg": (
                                        "$socioeconomic.indicators.available_income_eur"
                                    )
                                },
                                "average_rent_share_percent": {
                                    "$avg": (
                                        "$indicators.rent_as_share_of_available_income_percent"
                                    )
                                },
                                "average_monthly_remaining_eur": {
                                    "$avg": (
                                        "$indicators.monthly_remaining_after_rent_eur"
                                    )
                                },
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "territory_code": "$_id.territory_code",
                                "territory_name": "$_id.territory_name",
                                "municipality_count": 1,
                                "average_rent_eur": 1,
                                "average_annual_available_income_eur": 1,
                                "average_rent_share_percent": 1,
                                "average_monthly_remaining_eur": 1,
                            }
                        },
                        {"$sort": {"average_rent_share_percent": 1}},
                    ],
                    "ten_best_by_rent_share": [
                        {"$sort": {"indicators.rent_as_share_of_available_income_percent": 1}},
                        {"$limit": 10},
                        {
                            "$project": {
                                "_id": 0,
                                "municipality_code": 1,
                                "municipality_name": "$municipality.municipality_name",
                                "territory_name": "$municipality.territory.name",
                                "monthly_rent_eur": "$rental.monthly_eur",
                                "rent_share_percent": (
                                    "$indicators.rent_as_share_of_available_income_percent"
                                ),
                                "monthly_remaining_eur": (
                                    "$indicators.monthly_remaining_after_rent_eur"
                                ),
                            }
                        },
                    ],
                }
            },
        ],
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
    with mongo_connection() as (_, database):
        query_results = {}
        for spec in _query_specs():
            collection = database[spec["collection"]]
            cursor = collection.find(spec["filter"], spec["projection"])
            if spec["sort"]:
                cursor = cursor.sort(spec["sort"])
            if spec["limit"]:
                cursor = cursor.limit(spec["limit"])
            rows = list(cursor)
            query_results[spec["name"]] = {
                "collection": spec["collection"],
                "filter": spec["filter"],
                "projection": spec["projection"],
                "sort": spec["sort"],
                "result_count": len(rows),
                "results": rows,
            }

        pipeline_results = {}
        all_pipelines = {**pipeline_specs(), **youth_pipeline_specs()}
        for name, pipeline in all_pipelines.items():
            collection_name = (
                "salarios_juveniles"
                if name == "comparativa_salarial_y_esfuerzo_por_edad_2024"
                else "alquileres"
            )
            rows = list(
                database[collection_name].aggregate(pipeline, allowDiskUse=False)
            )
            pipeline_results[name] = {
                "collection": collection_name,
                "pipeline": pipeline,
                "result_count": len(rows),
                "results": rows,
            }

    _write_json(TABLES_PATH / "consultas_mongodb.json", query_results)
    _write_json(TABLES_PATH / "aggregations_mongodb.json", pipeline_results)
    logger.info(
        "Ejecutadas %s consultas y %s pipelines; resultados guardados en %s",
        len(query_results),
        len(pipeline_results),
        TABLES_PATH,
    )


if __name__ == "__main__":
    main()
