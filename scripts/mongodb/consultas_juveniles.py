from typing import Any

from bson.decimal128 import Decimal128


COMPARISON_YEAR = 2024
ZERO = Decimal128("0")
ONE_HUNDRED = Decimal128("100")
RECOMMENDED_SHARE = Decimal128("0.30")


def _municipality_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "municipios",
            "localField": "municipality_code",
            "foreignField": "_id",
            "as": "municipality",
        }
    }


def _population_lookup() -> dict[str, Any]:
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
                        "indicators.population": 1,
                    }
                },
            ],
            "as": "socioeconomic",
        }
    }


def _territorial_salary_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "salarios_juveniles",
            "let": {
                "territory_code": "$municipality.territory.code",
                "year": "$year",
            },
            "pipeline": [
                {
                    "$match": {
                        "indicator_code": 31,
                        "geography_level": "territory",
                        "age_group": "18-34",
                        "sex": "total",
                        "$expr": {
                            "$and": [
                                {"$eq": ["$territory_code", "$$territory_code"]},
                                {"$eq": ["$year", "$$year"]},
                            ]
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "territory_code": 1,
                        "net_monthly_salary_eur": 1,
                        "source": 1,
                    }
                },
            ],
            "as": "youth_salary",
        }
    }


def _youth_calculated_fields() -> dict[str, Any]:
    salary = "$youth_salary.net_monthly_salary_eur"
    rent = "$rental.monthly_eur"
    recommended_rent = {"$multiply": [salary, RECOMMENDED_SHARE]}
    return {
        "$addFields": {
            "indicators.rent_as_share_of_youth_salary_percent": {
                "$multiply": [{"$divide": [rent, salary]}, ONE_HUNDRED]
            },
            "indicators.money_remaining_after_rent_eur": {
                "$subtract": [salary, rent]
            },
            "indicators.recommended_max_rent_30_percent_eur": recommended_rent,
            "indicators.rent_minus_recommended_max_eur": {
                "$subtract": [rent, recommended_rent]
            },
        }
    }


def _municipal_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "$match": {
                "year": COMPARISON_YEAR,
                "geography.included_in_current_boundary_comparison": True,
                "rental.monthly_eur": {"$gt": ZERO},
            }
        },
        _municipality_lookup(),
        {"$unwind": "$municipality"},
        _territorial_salary_lookup(),
        {"$unwind": "$youth_salary"},
        _population_lookup(),
        {"$unwind": "$socioeconomic"},
        _youth_calculated_fields(),
        {
            "$project": {
                "_id": 0,
                "municipality_code": 1,
                "municipality_name": "$municipality.municipality_name",
                "territory_code": "$municipality.territory.code",
                "territory_name": "$municipality.territory.name",
                "year": 1,
                "population": "$socioeconomic.indicators.population",
                "deposit_count": "$rental.deposit_count",
                "monthly_rent_eur": "$rental.monthly_eur",
                "net_monthly_youth_salary_eur": (
                    "$youth_salary.net_monthly_salary_eur"
                ),
                "salary_territory_code": "$youth_salary.territory_code",
                "salary_scope": {"$literal": "territory_mean_applied_to_municipality"},
                "rent_as_share_of_youth_salary_percent": (
                    "$indicators.rent_as_share_of_youth_salary_percent"
                ),
                "money_remaining_after_rent_eur": (
                    "$indicators.money_remaining_after_rent_eur"
                ),
                "recommended_max_rent_30_percent_eur": (
                    "$indicators.recommended_max_rent_30_percent_eur"
                ),
                "rent_minus_recommended_max_eur": (
                    "$indicators.rent_minus_recommended_max_eur"
                ),
            }
        },
        {"$sort": {"rent_as_share_of_youth_salary_percent": 1}},
    ]


def _territory_salary_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "salarios_juveniles",
            "let": {"territory_code": "$territory_code"},
            "pipeline": [
                {
                    "$match": {
                        "indicator_code": 31,
                        "year": COMPARISON_YEAR,
                        "geography_level": "territory",
                        "age_group": "18-34",
                        "sex": "total",
                        "$expr": {
                            "$eq": ["$territory_code", "$$territory_code"]
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "net_monthly_salary_eur": 1,
                    }
                },
            ],
            "as": "youth_salary",
        }
    }


def _official_territory_benchmark_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "referencias_juventud",
            "let": {"territory_code": "$territory_code"},
            "pipeline": [
                {
                    "$match": {
                        "indicator_code": 49,
                        "metric": "rent_access_percent",
                        "year": COMPARISON_YEAR,
                        "geography_level": "territory",
                        "age_group": "18-34",
                        "sex": "total",
                        "$expr": {
                            "$eq": ["$territory_code", "$$territory_code"]
                        },
                    }
                },
                {"$project": {"_id": 0, "value": 1}},
            ],
            "as": "observatorio_benchmark",
        }
    }


def _territory_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "$match": {
                "year": COMPARISON_YEAR,
                "geography.included_in_current_boundary_comparison": True,
                "rental.monthly_eur": {"$gt": ZERO},
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
                "municipality_count": 1,
                "total_deposits": 1,
                "weighted_monthly_rent_eur": {
                    "$divide": ["$weighted_rent_sum", "$total_deposits"]
                },
            }
        },
        _territory_salary_lookup(),
        {"$unwind": "$youth_salary"},
        _official_territory_benchmark_lookup(),
        {"$unwind": "$observatorio_benchmark"},
        {
            "$addFields": {
                "net_monthly_youth_salary_eur": (
                    "$youth_salary.net_monthly_salary_eur"
                ),
                "calculated_rent_share_percent": {
                    "$multiply": [
                        {
                            "$divide": [
                                "$weighted_monthly_rent_eur",
                                "$youth_salary.net_monthly_salary_eur",
                            ]
                        },
                        ONE_HUNDRED,
                    ]
                },
                "observatorio_rent_share_percent": "$observatorio_benchmark.value",
            }
        },
        {
            "$addFields": {
                "difference_percentage_points": {
                    "$subtract": [
                        "$calculated_rent_share_percent",
                        "$observatorio_rent_share_percent",
                    ]
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "territory_code": 1,
                "territory_name": 1,
                "year": {"$literal": COMPARISON_YEAR},
                "municipality_count": 1,
                "total_deposits": 1,
                "weighted_monthly_rent_eur": 1,
                "net_monthly_youth_salary_eur": 1,
                "calculated_rent_share_percent": 1,
                "observatorio_rent_share_percent": 1,
                "difference_percentage_points": 1,
            }
        },
        {"$sort": {"territory_code": 1}},
    ]


def _age_benchmark_lookup() -> dict[str, Any]:
    return {
        "$lookup": {
            "from": "referencias_juventud",
            "let": {"age_group": "$age_group"},
            "pipeline": [
                {
                    "$match": {
                        "indicator_code": 49,
                        "metric": "rent_access_percent",
                        "year": COMPARISON_YEAR,
                        "geography_level": "euskadi",
                        "age_group": {"$in": ["18-29", "30-34"]},
                        "sex": "total",
                        "$expr": {"$eq": ["$age_group", "$$age_group"]},
                    }
                },
                {"$project": {"_id": 0, "value": 1}},
            ],
            "as": "official_rent_share",
        }
    }


def _age_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "$match": {
                "indicator_code": 31,
                "year": COMPARISON_YEAR,
                "geography_level": "euskadi",
                "age_group": {"$in": ["18-29", "30-34"]},
                "sex": "total",
            }
        },
        _age_benchmark_lookup(),
        {"$unwind": "$official_rent_share"},
        {
            "$project": {
                "_id": 0,
                "year": 1,
                "age_group": 1,
                "net_monthly_youth_salary_eur": "$net_monthly_salary_eur",
                "observatorio_rent_share_percent": "$official_rent_share.value",
                "comparison_scope": {
                    "$literal": "Euskadi, published age margins only"
                },
            }
        },
        {"$sort": {"age_group": 1}},
    ]


def youth_pipeline_specs() -> dict[str, list[dict[str, Any]]]:
    return {
        "municipios_ordenados_por_esfuerzo_alquiler_salario_joven_2024": (
            _municipal_pipeline()
        ),
        "comparativa_territorial_salario_joven_2024": _territory_pipeline(),
        "comparativa_salarial_y_esfuerzo_por_edad_2024": _age_pipeline(),
    }
