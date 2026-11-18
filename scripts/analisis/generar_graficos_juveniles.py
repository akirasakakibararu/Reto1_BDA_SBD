import csv
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from scripts.analisis.calcular_indicadores_juveniles import (
    AGE_PATH,
    MUNICIPAL_PATH,
    TERRITORY_PATH,
)
from scripts.mongodb.mongo_comun import ROOT


CHARTS_PATH = ROOT / "resultados" / "graficos"


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Ejecute primero el análisis juvenil de MongoDB: {path}"
        )
    with path.open(encoding="utf-8-sig", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    if not rows:
        raise ValueError(f"No hay filas para generar el gráfico: {path}")
    return rows


def _save(figure: plt.Figure, filename: str) -> None:
    CHARTS_PATH.mkdir(parents=True, exist_ok=True)
    destination = CHARTS_PATH / filename
    figure.savefig(destination, dpi=180, bbox_inches="tight")
    plt.close(figure)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"No se generó correctamente el gráfico: {destination}")


def _plot_municipal_burden(
    rows: list[dict[str, str]], extremes_only: bool = False
) -> None:
    ordered = sorted(
        rows,
        key=lambda row: float(row["rent_as_share_of_youth_salary_percent"]),
    )
    if extremes_only and len(ordered) > 20:
        ordered = ordered[:10] + ordered[-10:]
    figure_height = (
        max(7, len(ordered) * 0.42)
        if extremes_only
        else max(17, len(ordered) * 0.24)
    )
    figure, axis = plt.subplots(figsize=(12, figure_height))
    values = [
        float(row["rent_as_share_of_youth_salary_percent"]) for row in ordered
    ]
    colors = ["#26856b" if value <= 30 else "#bc5b54" for value in values]
    axis.barh(
        [row["municipality_name"] for row in ordered],
        values,
        color=colors,
    )
    axis.invert_yaxis()
    axis.axvline(30, color="#333333", linestyle="--", linewidth=1.2, label="30%")
    axis.set_title(
        "Alquiler sobre salario juvenil neto por municipio (2024)\n"
        + (
            "10 municipios con menor y 10 con mayor esfuerzo\n"
            if extremes_only
            else ""
        )
        + "Salario medio territorial asignado; no observado a nivel municipal"
    )
    axis.set_xlabel("Porcentaje del salario neto mensual (18-34)")
    axis.set_ylabel("Municipio")
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=100))
    axis.grid(axis="x", alpha=0.25)
    axis.legend()
    axis.tick_params(axis="y", labelsize=9 if extremes_only else 6.5)
    _save(
        figure,
        "esfuerzo_alquiler_salario_juvenil_municipios_2024"
        + ("_10_menores_y_10_mayores" if extremes_only else "")
        + ".png",
    )


def _plot_remaining_income(
    rows: list[dict[str, str]], extremes_only: bool = False
) -> None:
    ordered = sorted(
        rows,
        key=lambda row: float(row["money_remaining_after_rent_eur"]),
    )
    if extremes_only and len(ordered) > 20:
        ordered = ordered[:10] + ordered[-10:]
    figure_height = (
        max(7, len(ordered) * 0.42)
        if extremes_only
        else max(17, len(ordered) * 0.24)
    )
    figure, axis = plt.subplots(figsize=(12, figure_height))
    values = [float(row["money_remaining_after_rent_eur"]) for row in ordered]
    colors = ["#bc5b54" if value < 0 else "#26856b" for value in values]
    axis.barh(
        [row["municipality_name"] for row in ordered],
        values,
        color=colors,
    )
    axis.axvline(0, color="#333333", linewidth=1)
    axis.set_title(
        "Salario juvenil neto restante tras pagar el alquiler (2024)\n"
        + (
            "10 municipios con menor y 10 con mayor cantidad restante\n"
            if extremes_only
            else ""
        )
        + "Antes de suministros y otros gastos"
    )
    axis.set_xlabel("Euros mensuales")
    axis.set_ylabel("Municipio")
    axis.grid(axis="x", alpha=0.25)
    axis.tick_params(axis="y", labelsize=9 if extremes_only else 6.5)
    _save(
        figure,
        "dinero_restante_salario_juvenil_municipios_2024"
        + ("_10_menores_y_10_mayores" if extremes_only else "")
        + ".png",
    )


def _plot_salary_and_rent(rows: list[dict[str, str]]) -> None:
    ordered = sorted(rows, key=lambda row: row["territory_code"])
    labels = [row["territory_name"] for row in ordered]
    salaries = [
        float(row["net_monthly_youth_salary_eur"]) for row in ordered
    ]
    rents = [float(row["weighted_monthly_rent_eur"]) for row in ordered]
    positions = list(range(len(ordered)))
    width = 0.38
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.bar(
        [position - width / 2 for position in positions],
        salaries,
        width,
        label="Salario juvenil neto medio",
        color="#3178a8",
    )
    axis.bar(
        [position + width / 2 for position in positions],
        rents,
        width,
        label="Alquiler medio ponderado por fianzas",
        color="#d58a32",
    )
    axis.set_xticks(positions, labels)
    axis.set_title("Salario juvenil y alquiler medio por territorio (2024)")
    axis.set_ylabel("Euros al mes")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    figure.text(
        0.01,
        0.01,
        "Alquiler: media ponderada de municipios EMAL publicados, no todo el parque.",
        fontsize=8,
    )
    _save(figure, "salario_y_alquiler_juvenil_territorios_2024.png")


def _plot_territory_benchmark(rows: list[dict[str, str]]) -> None:
    ordered = sorted(rows, key=lambda row: row["territory_code"])
    labels = [row["territory_name"] for row in ordered]
    calculated = [
        float(row["calculated_rent_share_percent"]) for row in ordered
    ]
    official = [
        float(row["observatorio_rent_share_percent"]) for row in ordered
    ]
    positions = list(range(len(ordered)))
    width = 0.36
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.bar(
        [position - width / 2 for position in positions],
        calculated,
        width,
        label="Cálculo propio: EMAL municipal ponderado / salario OVJ",
        color="#3178a8",
    )
    axis.bar(
        [position + width / 2 for position in positions],
        official,
        width,
        label="Observatorio Vasco de la Juventud, indicador 49",
        color="#bc5b54",
    )
    axis.set_xticks(positions, labels)
    axis.set_ylabel("Porcentaje del salario neto")
    axis.set_title("Contraste territorial del esfuerzo de alquiler (2024)")
    axis.legend(fontsize=8)
    axis.grid(axis="y", alpha=0.25)
    _save(figure, "contraste_esfuerzo_juvenil_ovj_territorios_2024.png")


def _plot_age_comparison(rows: list[dict[str, str]]) -> None:
    ordered = sorted(rows, key=lambda row: row["age_group"])
    labels = [row["age_group"] for row in ordered]
    salaries = [
        float(row["net_monthly_youth_salary_eur"]) for row in ordered
    ]
    burdens = [
        float(row["observatorio_rent_share_percent"]) for row in ordered
    ]
    figure, axes = plt.subplots(1, 2, figsize=(11, 5))
    axes[0].bar(labels, salaries, color="#3178a8")
    axes[0].set_title("Salario neto mensual")
    axes[0].set_ylabel("Euros")
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(labels, burdens, color="#d58a32")
    axes[1].set_title("Esfuerzo oficial de alquiler (indicador 49)")
    axes[1].set_ylabel("Porcentaje del salario")
    axes[1].yaxis.set_major_formatter(PercentFormatter(xmax=100))
    axes[1].grid(axis="y", alpha=0.25)
    figure.suptitle("Indicadores de juventud por edad, Euskadi (2024)")
    figure.text(
        0.01,
        0.01,
        "Solo se comparan grupos publicados con igual definición; no hay "
        "desglose edad × territorio.",
        fontsize=8,
    )
    _save(figure, "comparacion_juvenil_por_edad_2024.png")


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
    municipalities = _read_rows(MUNICIPAL_PATH)
    territories = _read_rows(TERRITORY_PATH)
    age_groups = _read_rows(AGE_PATH)
    if len(municipalities) < 3 or len(territories) != 3 or len(age_groups) != 2:
        raise RuntimeError(
            "Las tablas juveniles no tienen la cobertura esperada para los gráficos."
        )
    _plot_municipal_burden(municipalities)
    _plot_municipal_burden(municipalities, extremes_only=True)
    _plot_remaining_income(municipalities)
    _plot_remaining_income(municipalities, extremes_only=True)
    _plot_salary_and_rent(territories)
    _plot_territory_benchmark(territories)
    _plot_age_comparison(age_groups)
    logging.getLogger("reto_vivienda.analisis.juventud").info(
        "Generados cinco gráficos juveniles desde las tablas exportadas de MongoDB."
    )


if __name__ == "__main__":
    main()
