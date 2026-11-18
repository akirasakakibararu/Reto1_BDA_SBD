import csv
import json
import logging
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128

from scripts.mongodb.consultas import pipeline_specs
from scripts.mongodb.mongo_comun import ROOT, mongo_connection


YEAR = 2023
INDICATORS_PATH = ROOT / "resultados" / "indicadores"
CSV_PATH = INDICATORS_PATH / "indicadores_municipales_2023.csv"
REPORT_PATH = INDICATORS_PATH / "resumen_emancipacion_2023.json"
PIPELINE_NAME = "municipios_ordenados_por_esfuerzo_de_alquiler_2023"


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if value is None:
        raise ValueError("No se puede calcular un indicador con un valor nulo.")
    return Decimal(str(value))


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "municipality_code",
        "municipality_name",
        "territory_name",
        "year",
        "population",
        "deposit_count",
        "monthly_rent_eur",
        "rent_per_m2_eur",
        "available_income_annual_eur",
        "monthly_available_income_eur",
        "annual_rent_eur",
        "rent_as_share_of_available_income_percent",
        "monthly_available_income_after_rent_eur",
        "monthly_income_units_to_cover_annual_rent",
        "income_measure",
    ]
    INDICATORS_PATH.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=INDICATORS_PATH,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(
                temporary_file,
                fieldnames=fieldnames,
                lineterminator="\n",
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(rows)
        temporary_path.replace(CSV_PATH)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _display_record(record: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "municipality_code",
        "municipality_name",
        "territory_name",
        "monthly_rent_eur",
        "rent_as_share_of_available_income_percent",
        "monthly_available_income_after_rent_eur",
        "available_income_annual_eur",
        "population",
    )
    return {field: record[field] for field in fields}


def _write_json(report: dict[str, Any]) -> None:
    INDICATORS_PATH.mkdir(parents=True, exist_ok=True)
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
            logging.FileHandler(ROOT / "logs" / "analisis.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("reto_vivienda.analisis")
    pipeline = pipeline_specs()[PIPELINE_NAME]
    with mongo_connection() as (_, database):
        raw_rows = list(database["alquileres"].aggregate(pipeline))
    if not raw_rows:
        raise RuntimeError("La agregación no devolvió municipios comparables.")

    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    with localcontext() as context:
        context.prec = 34
        for raw in raw_rows:
            code = raw["municipality_code"]
            if code in seen_codes:
                raise ValueError(f"Municipio repetido en el análisis: {code}")
            seen_codes.add(code)
            monthly_rent = _decimal(raw["monthly_rent_eur"])
            rent_per_m2 = _decimal(raw["rent_per_m2_eur"])
            annual_income = _decimal(raw["available_income_annual_eur"])
            monthly_income = _decimal(raw["monthly_available_income_eur"])
            rent_share = _decimal(
                raw["rent_as_share_of_available_income_percent"]
            )
            monthly_remaining = _decimal(
                raw["monthly_remaining_after_rent_eur"]
            )
            if annual_income <= 0 or monthly_income <= 0 or monthly_rent <= 0:
                raise ValueError(f"Valor no positivo en indicadores de {code}.")

            expected_monthly_income = annual_income / Decimal(12)
            expected_share = monthly_rent / expected_monthly_income * Decimal(100)
            expected_remaining = expected_monthly_income - monthly_rent
            if abs(monthly_income - expected_monthly_income) > Decimal("1e-28"):
                raise ValueError(f"Conversión anual/mensual no coherente para {code}.")
            if abs(rent_share - expected_share) > Decimal("1e-26"):
                raise ValueError(f"Porcentaje de alquiler no coherente para {code}.")
            if abs(monthly_remaining - expected_remaining) > Decimal("1e-28"):
                raise ValueError(f"Resto mensual no coherente para {code}.")

            annual_rent = monthly_rent * Decimal(12)
            monthly_income_units = annual_rent / monthly_income
            rows.append(
                {
                    "municipality_code": code,
                    "municipality_name": raw["municipality_name"],
                    "territory_name": raw["territory_name"],
                    "year": YEAR,
                    "population": int(raw["population"]),
                    "deposit_count": int(raw["deposit_count"]),
                    "monthly_rent_eur": _format_decimal(monthly_rent),
                    "rent_per_m2_eur": _format_decimal(rent_per_m2),
                    "available_income_annual_eur": _format_decimal(annual_income),
                    "monthly_available_income_eur": _format_decimal(monthly_income),
                    "annual_rent_eur": _format_decimal(annual_rent),
                    "rent_as_share_of_available_income_percent": _format_decimal(
                        rent_share
                    ),
                    "monthly_available_income_after_rent_eur": _format_decimal(
                        monthly_remaining
                    ),
                    "monthly_income_units_to_cover_annual_rent": _format_decimal(
                        monthly_income_units
                    ),
                    "income_measure": raw["income_measure"],
                }
            )

    rows.sort(
        key=lambda row: Decimal(
            row["rent_as_share_of_available_income_percent"]
        )
    )
    if len(rows) < 3:
        raise RuntimeError(
            f"Se requieren al menos tres municipios comparables; hay {len(rows)}."
        )
    _write_csv(rows)

    cheapest_rent = sorted(rows, key=lambda row: Decimal(row["monthly_rent_eur"]))
    remaining = sorted(
        rows,
        key=lambda row: Decimal(row["monthly_available_income_after_rent_eur"]),
        reverse=True,
    )
    median = rows[len(rows) // 2]
    report = {
        "status": "verified",
        "database": "reto_vivienda",
        "reference_year": YEAR,
        "municipalities_compared": len(rows),
        "source_measure_warning": (
            "La renta personal disponible media es de residentes de 18+ años; "
            "no es salario juvenil ni nómina individual."
        ),
        "period_comparability_warning": (
            "La comparación usa el año publicado 2023 de ambas series. EMAL "
            "advierte que rentas históricas pueden actualizarse por IRAV y ser "
            "provisionales; no equivale a una nómina neta juvenil contemporánea."
        ),
        "single_person_assumption": (
            "Compara una renta mensual de contrato con la renta disponible media "
            "anual por persona adulta dividida entre 12; no incorpora gastos "
            "distintos del alquiler ni ingresos de otros convivientes."
        ),
        "formulas": {
            "monthly_available_income_eur": "available_income_annual_eur / 12",
            "annual_rent_eur": "monthly_rent_eur * 12",
            "rent_as_share_of_available_income_percent": (
                "monthly_rent_eur / monthly_available_income_eur * 100"
            ),
            "monthly_available_income_after_rent_eur": (
                "monthly_available_income_eur - monthly_rent_eur"
            ),
            "monthly_income_units_to_cover_annual_rent": (
                "annual_rent_eur / monthly_available_income_eur"
            ),
        },
        "best_three_by_rent_share": [_display_record(row) for row in rows[:3]],
        "median_municipality_by_rent_share": _display_record(median),
        "worst_three_by_rent_share": [_display_record(row) for row in rows[-3:]],
        "three_lowest_rents": [_display_record(row) for row in cheapest_rent[:3]],
        "three_highest_monthly_amounts_after_rent": [
            _display_record(row) for row in remaining[:3]
        ],
        "outputs": [str(CSV_PATH.relative_to(ROOT)), str(REPORT_PATH.relative_to(ROOT))],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(report)
    logger.info(
        "Calculados indicadores para %s municipios con datos reales de MongoDB.",
        len(rows),
    )


if __name__ == "__main__":
    main()
