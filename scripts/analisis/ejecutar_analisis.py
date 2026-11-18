from scripts.analisis.calcular_indicadores import main as calcular_indicadores
from scripts.analisis.calcular_indicadores_juveniles import (
    main as calcular_indicadores_juveniles,
)
from scripts.analisis.generar_graficos import main as generar_graficos
from scripts.analisis.generar_graficos_juveniles import (
    main as generar_graficos_juveniles,
)
from scripts.mongodb.consultas import main as ejecutar_consultas


def main() -> None:
    ejecutar_consultas()
    calcular_indicadores()
    calcular_indicadores_juveniles()
    generar_graficos()
    generar_graficos_juveniles()


if __name__ == "__main__":
    main()
