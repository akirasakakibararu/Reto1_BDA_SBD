import csv
import json
import logging
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128

from scripts.mongodb.consultas_juveniles import youth_pipeline_specs
from scripts.mongodb.mongo_comun import ROOT, mongo_connection


YEAR = 2024
INDICATORS_PATH = ROOT / "resultados" / "indicadores"
TABLES_PATH = ROOT / "resultados" / "tablas"
MUNICIPAL_PATH = (
    INDICATORS_PATH / "indicadores_juveniles_municipales_2024.csv"
)
TERRITORY_PATH = (
    TABLES_PATH / "comparativa_juvenil_territorial_2024.csv"
)
AGE_PATH = TABLES_PATH / "comparativa_juvenil_edad_2024.csv"
REPORT_PATH = (
    INDICATORS_PATH / "resumen_emancipacion_juvenil_2024.json"
)
MUNICIPAL_PIPELINE = (
    "municipios_ordenados_por_esfuerzo_alquiler_salario_joven_2024"
)
TERRITORY_PIPELINE = "comparativa_territorial_salario_joven_2024"
AGE_PIPELINE = "comparativa_salarial_y_esfuerzo_por_edad_2024"
MUNICIPAL_FIELDS = [
    "municipality_code",
    "municipality_name",
    "territory_code",
    "territory_name",
    "year",
    "population",
    "deposit_count",
    "monthly_rent_eur",
    "net_monthly_youth_salary_eur",
    "salary_scope",
    "rent_as_share_of_youth_salary_percent",
    "money_remaining_after_rent_eur",
    "recommended_max_rent_30_percent_eur",
    "rent_minus_recommended_max_eur",
]
TERRITORY_FIELDS = [
    "territory_code",
    "territory_name",
    "year",
    "municipality_count",
    "total_deposits",
    "weighted_monthly_rent_eur",
    "net_monthly_youth_salary_eur",
    "calculated_rent_share_percent",
    "observatorio_rent_share_percent",
    "difference_percentage_points",
]
AGE_FIELDS = [
    "year",
    "age_group",
    "net_monthly_youth_salary_eur",
    "observatorio_rent_share_percent",
    "comparison_scope",
]


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if value is None:
        raise ValueError("No se puede calcular un indicador con un valor nulo.")
    return Decimal(str(value))


def _format_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _export_row(raw: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    result = {}
    for field in fields:
        value = raw[field]
        if isinstance(value, Decimal128):
            value = _format_decimal(value.to_decimal())
        result[field] = value
    return result


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(
                temporary_file,
                fieldnames=fields,
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        temporary_path.replace(path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _write_json(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_municipal_rows(
    rows: list[dict[str, Any]], expected_count: int
) -> None:
    if len(rows) != expected_count or len(rows) < 3:
        raise RuntimeError(
            "La agregación no conserva la cobertura EMAL con alquiler positivo: "
            f"esperados={expected_count}, obtenidos={len(rows)}."
        )
    codes = [row["municipality_code"] for row in rows]
    if len(codes) != len(set(codes)):
        raise ValueError("Hay municipios duplicados en el análisis juvenil.")
    with localcontext() as context:
        context.prec = 34
        tolerance = Decimal("1e-25")
        for row in rows:
            if row["year"] != YEAR:
                raise ValueError("Se mezclaron años en la comparación municipal.")
            if row["territory_code"] != row["salary_territory_code"]:
                raise ValueError(
                    "El código territorial del salario no coincide con el municipio "
                    f"{row['municipality_code']}."
                )
            if not row["population"] or not row["deposit_count"]:
                raise ValueError(
                    f"Falta población o número de fianzas para {row['municipality_code']}."
                )
            rent = _decimal(row["monthly_rent_eur"])
            salary = _decimal(row["net_monthly_youth_salary_eur"])
            if rent <= 0 or salary <= 0:
                raise ValueError(
                    f"Hay un valor monetario no positivo para {row['municipality_code']}."
                )
            expected_share = rent / salary * Decimal(100)
            expected_remaining = salary - rent
            expected_cap = salary * Decimal("0.30")
            expected_difference = rent - expected_cap
            checks = (
                (
                    "rent_as_share_of_youth_salary_percent",
                    expected_share,
                ),
                ("money_remaining_after_rent_eur", expected_remaining),
                ("recommended_max_rent_30_percent_eur", expected_cap),
                ("rent_minus_recommended_max_eur", expected_difference),
            )
            for field, expected in checks:
                if abs(_decimal(row[field]) - expected) > tolerance:
                    raise ValueError(
                        f"Fórmula inconsistente en {field} para "
                        f"{row['municipality_code']}."
                    )


def _validate_territory_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 3 or {row["territory_code"] for row in rows} != {
        "01",
        "20",
        "48",
    }:
        raise RuntimeError("La comparación debe incluir los tres territorios.")
    for row in rows:
        if row["observatorio_rent_share_percent"] is None:
            raise ValueError(
                f"Falta el contraste del Observatorio para {row['territory_code']}."
            )
        expected_delta = (
            _decimal(row["calculated_rent_share_percent"])
            - _decimal(row["observatorio_rent_share_percent"])
        )
        if abs(
            _decimal(row["difference_percentage_points"]) - expected_delta
        ) > Decimal("1e-25"):
            raise ValueError(
                f"Diferencia incoherente para el territorio {row['territory_code']}."
            )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                ROOT / "logs" / "analisis.log",
                encoding="utf-8",
            ),
        ],
    )
    logger = logging.getLogger("reto_vivienda.analisis.juventud")
    pipelines = youth_pipeline_specs()
    with mongo_connection() as (_, database):
        rent_filter = {
            "year": YEAR,
            "geography.included_in_current_boundary_comparison": True,
        }
        source_rents = list(
            database["alquileres"].find(
                rent_filter,
                {
                    "_id": 0,
                    "municipality_code": 1,
                    "municipality_name": 1,
                    "rental.monthly_eur": 1,
                },
            )
        )
        municipal_raw = list(
            database["alquileres"].aggregate(
                pipelines[MUNICIPAL_PIPELINE], allowDiskUse=False
            )
        )
        territory_raw = list(
            database["alquileres"].aggregate(
                pipelines[TERRITORY_PIPELINE], allowDiskUse=False
            )
        )
        age_raw = list(
            database["salarios_juveniles"].aggregate(
                pipelines[AGE_PIPELINE], allowDiskUse=False
            )
        )

    if not municipal_raw or not territory_raw or not age_raw:
        raise RuntimeError(
            "MongoDB devolvió una agregación juvenil vacía; cargue primero "
            "los indicadores oficiales."
        )
    eligible_rents = [
        row
        for row in source_rents
        if row.get("rental", {}).get("monthly_eur") is not None
        and _decimal(row["rental"]["monthly_eur"]) > 0
    ]
    excluded_rents = [
        {
            "municipality_code": row["municipality_code"],
            "municipality_name": row["municipality_name"],
            "reason": "EMAL 2024 does not publish a positive monthly rent value.",
        }
        for row in source_rents
        if row.get("rental", {}).get("monthly_eur") is None
        or _decimal(row["rental"]["monthly_eur"]) <= 0
    ]
    _validate_municipal_rows(municipal_raw, len(eligible_rents))
    _validate_territory_rows(territory_raw)
    if {row["age_group"] for row in age_raw} != {"18-29", "30-34"}:
        raise RuntimeError("La comparación de edad no contiene los dos grupos válidos.")

    municipal_rows = [
        _export_row(row, MUNICIPAL_FIELDS) for row in municipal_raw
    ]
    territory_rows = [
        _export_row(row, TERRITORY_FIELDS) for row in territory_raw
    ]
    age_rows = [_export_row(row, AGE_FIELDS) for row in age_raw]
    _write_csv(MUNICIPAL_PATH, MUNICIPAL_FIELDS, municipal_rows)
    _write_csv(TERRITORY_PATH, TERRITORY_FIELDS, territory_rows)
    _write_csv(AGE_PATH, AGE_FIELDS, age_rows)

    best = municipal_rows[:3]
    worst = municipal_rows[-3:]
    burden_over_30 = sum(
        _decimal(row["rent_as_share_of_youth_salary_percent"])
        > Decimal(30)
        for row in municipal_raw
    )
    negative_remainder = sum(
        _decimal(row["money_remaining_after_rent_eur"]) < 0
        for row in municipal_raw
    )
    report = {
        "status": "verified",
        "database": "reto_vivienda",
        "reference_year": YEAR,
        "municipalities_compared": len(municipal_rows),
        "municipalities_with_emal_record": len(source_rents),
        "municipalities_excluded_due_to_missing_rent": excluded_rents,
        "income_measure": (
            "Official mean net monthly salary of salaried 18-34 year-olds "
            "by historical territory; not municipality-observed."
        ),
        "municipality_scope_warning": (
            "Each municipality is assigned the 18-34 salary mean of its territory "
            "using official territory codes; this does not assert an observed "
            "municipal salary."
        ),
        "comparison_period_warning": (
            "The main comparison joins 2024 EMAL rental and population data with "
            "2024 youth salary data."
        ),
        "single_person_assumption": (
            "A single person pays the full monthly rental contract; utilities, "
            "food, transport, deposits and other costs are excluded."
        ),
        "thirty_percent_reference_warning": (
            "The 30% rent-to-income threshold is an analytical reference, not a "
            "guarantee of affordability or an official eligibility rule."
        ),
        "formulas": {
            "rent_as_share_of_youth_salary_percent": (
                "monthly_rent_eur / net_monthly_youth_salary_eur * 100"
            ),
            "money_remaining_after_rent_eur": (
                "net_monthly_youth_salary_eur - monthly_rent_eur"
            ),
            "recommended_max_rent_30_percent_eur": (
                "net_monthly_youth_salary_eur * 0.30"
            ),
            "rent_minus_recommended_max_eur": (
                "monthly_rent_eur - recommended_max_rent_30_percent_eur"
            ),
        },
        "municipalities_over_30_percent": int(burden_over_30),
        "municipalities_with_negative_remainder": int(negative_remainder),
        "best_three_by_rent_share": best,
        "worst_three_by_rent_share": worst,
        "territory_comparison": territory_rows,
        "age_group_comparison": age_rows,
        "outputs": [
            str(MUNICIPAL_PATH.relative_to(ROOT)),
            str(TERRITORY_PATH.relative_to(ROOT)),
            str(AGE_PATH.relative_to(ROOT)),
            str(REPORT_PATH.relative_to(ROOT)),
        ],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(report)
    logger.info(
        "Indicadores juveniles verificados para %s municipios y %s territorios.",
        len(municipal_rows),
        len(territory_rows),
    )


if __name__ == "__main__":
    main()
