import csv
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from bson.decimal128 import Decimal128

from scripts.mongodb.consultas import pipeline_specs
from scripts.mongodb.mongo_comun import ROOT, mongo_connection


INDICATORS_PATH = ROOT / "resultados" / "indicadores" / "indicadores_municipales_2023.csv"
TABLES_PATH = ROOT / "resultados" / "tablas"
CHARTS_PATH = ROOT / "resultados" / "graficos"
TREND_PATH = TABLES_PATH / "evolucion_alquiler_ponderada_territorio.csv"
TERRITORY_PATH = TABLES_PATH / "comparativa_territorial_2023.csv"
TREND_PIPELINE = "evolucion_del_alquiler_ponderada_por_fianzas_y_territorio"
TERRITORY_PIPELINE = "resumen_de_emancipacion_por_territorio_2023"


def _decimal(value: Any) -> float:
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    return float(value)


def _read_indicator_rows() -> list[dict[str, str]]:
    if not INDICATORS_PATH.is_file():
        raise FileNotFoundError(
            f"Ejecute primero el cálculo de indicadores: {INDICATORS_PATH}"
        )
    with INDICATORS_PATH.open(encoding="utf-8-sig", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    if len(rows) < 3:
        raise ValueError("No hay suficientes municipios para generar los gráficos.")
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=fields,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _save_figure(figure: plt.Figure, filename: str) -> None:
    CHARTS_PATH.mkdir(parents=True, exist_ok=True)
    output_path = CHARTS_PATH / filename
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"No se generó correctamente el gráfico: {output_path}")


def _plot_lowest_rents(rows: list[dict[str, str]]) -> None:
    selected = sorted(rows, key=lambda row: float(row["monthly_rent_eur"]))[:10]
    selected.reverse()
    figure, axis = plt.subplots(figsize=(11, 7))
    axis.barh(
        [row["municipality_name"] for row in selected],
        [float(row["monthly_rent_eur"]) for row in selected],
        color="#3178a8",
    )
    axis.set_title("Diez alquileres mensuales medios más bajos (2023)")
    axis.set_xlabel("Euros al mes por contrato")
    axis.set_ylabel("Municipio")
    axis.grid(axis="x", alpha=0.25)
    figure.text(
        0.01,
        0.01,
        "Fuente: EMAL. Municipios publicados; valores históricos sujetos a notas metodológicas.",
        fontsize=8,
    )
    _save_figure(figure, "alquileres_mas_bajos_2023.png")


def _plot_rent_share(rows: list[dict[str, str]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: float(
            row["rent_as_share_of_available_income_percent"]
        ),
    )
    selected = ordered[:10] + ordered[-10:]
    selected.sort(
        key=lambda row: float(
            row["rent_as_share_of_available_income_percent"]
        )
    )
    colors = [
        "#26856b" if row in ordered[:10] else "#bc5b54"
        for row in selected
    ]
    figure, axis = plt.subplots(figsize=(12, 9))
    axis.barh(
        [row["municipality_name"] for row in selected],
        [
            float(row["rent_as_share_of_available_income_percent"])
            for row in selected
        ],
        color=colors,
    )
    axis.set_title("Alquiler como porcentaje de la renta disponible media (2023)")
    axis.set_xlabel("Porcentaje de la renta disponible media adulta")
    axis.set_ylabel("Municipio")
    axis.grid(axis="x", alpha=0.25)
    figure.text(
        0.01,
        0.01,
        "Comparación de los 10 mejores y 10 peores resultados. "
        "La renta disponible media de residentes 18+ no es salario juvenil.",
        fontsize=8,
    )
    _save_figure(figure, "esfuerzo_alquiler_mejores_y_peores_2023.png")


def _plot_amount_after_rent(rows: list[dict[str, str]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: float(
            row["monthly_available_income_after_rent_eur"]
        ),
    )
    selected = ordered[:10] + ordered[-10:]
    selected.sort(
        key=lambda row: float(
            row["monthly_available_income_after_rent_eur"]
        )
    )
    colors = [
        "#bc5b54" if row in ordered[:10] else "#26856b"
        for row in selected
    ]
    figure, axis = plt.subplots(figsize=(12, 9))
    axis.barh(
        [row["municipality_name"] for row in selected],
        [
            float(row["monthly_available_income_after_rent_eur"])
            for row in selected
        ],
        color=colors,
    )
    axis.set_title("Renta disponible media mensual estimada tras el alquiler (2023)")
    axis.set_xlabel("Euros al mes, antes de otros gastos")
    axis.set_ylabel("Municipio")
    axis.grid(axis="x", alpha=0.25)
    figure.text(
        0.01,
        0.01,
        "Proxy por persona adulta: renta anual disponible / 12 - alquiler mensual.",
        fontsize=8,
    )
    _save_figure(figure, "renta_disponible_tras_alquiler_2023.png")


def _plot_weighted_rent_trend(rows: list[dict[str, Any]]) -> None:
    figure, axis = plt.subplots(figsize=(11, 7))
    territories = sorted({row["territory_name"] for row in rows})
    for territory in territories:
        series = sorted(
            (row for row in rows if row["territory_name"] == territory),
            key=lambda row: int(row["year"]),
        )
        axis.plot(
            [int(row["year"]) for row in series],
            [_decimal(row["weighted_monthly_rent_eur"]) for row in series],
            marker="o",
            linewidth=2,
            label=territory,
        )
    axis.set_title("Evolución del alquiler medio ponderado por fianzas")
    axis.set_xlabel("Año de inicio del contrato")
    axis.set_ylabel("Euros al mes")
    axis.legend(title="Territorio histórico")
    axis.grid(alpha=0.25)
    figure.text(
        0.01,
        0.01,
        "Media ponderada por número de fianzas EMAL; geografía actual de Galdakao.",
        fontsize=8,
    )
    _save_figure(figure, "evolucion_alquiler_ponderada_2016_2025.png")


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
    indicator_rows = _read_indicator_rows()
    specs = pipeline_specs()
    with mongo_connection() as (_, database):
        trend_rows = list(
            database["alquileres"].aggregate(specs[TREND_PIPELINE])
        )
        territory_result = list(
            database["alquileres"].aggregate(specs[TERRITORY_PIPELINE])
        )
    if not trend_rows:
        raise RuntimeError("La agregación de evolución del alquiler está vacía.")
    if len(territory_result) != 1:
        raise RuntimeError("La comparación territorial no devolvió un único faceteo.")
    territory_rows = territory_result[0]["resumen_territorial"]
    if not territory_rows:
        raise RuntimeError("La agregación territorial no contiene resultados.")

    _write_csv(
        TREND_PATH,
        trend_rows,
        [
            "territory_code",
            "territory_name",
            "year",
            "weighted_monthly_rent_eur",
            "total_deposits",
            "municipality_count",
        ],
    )
    _write_csv(
        TERRITORY_PATH,
        territory_rows,
        [
            "territory_code",
            "territory_name",
            "municipality_count",
            "average_rent_eur",
            "average_annual_available_income_eur",
            "average_rent_share_percent",
            "average_monthly_remaining_eur",
        ],
    )
    _plot_lowest_rents(indicator_rows)
    _plot_rent_share(indicator_rows)
    _plot_amount_after_rent(indicator_rows)
    _plot_weighted_rent_trend(trend_rows)
    logger.info(
        "Generados 4 gráficos y 2 tablas desde %s municipios y %s datos territoriales.",
        len(indicator_rows),
        len(trend_rows),
    )


if __name__ == "__main__":
    main()
