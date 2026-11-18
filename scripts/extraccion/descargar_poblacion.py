import argparse

from .descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://opendata.euskadi.eus/contenidos/estadistica/"
    "udalmap_indicador_162/es_def/adjuntos/indicator.csv"
)
DESTINO = (
    ROOT
    / "datos"
    / "originales"
    / "poblacion"
    / "udalmap_poblacion_total.csv"
)
FUENTE = {
    "source": "Udalmap, indicador 162 - población total",
    "publisher": "Gobierno Vasco",
    "format": "CSV original",
    "license": "CC BY 4.0",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga el CSV original de población total Udalmap."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vuelve a descargar y sustituye el archivo local.",
    )
    args = parser.parse_args()
    configurar_logging()
    descargar_archivo(URL, DESTINO, FUENTE, forzar=args.force)


if __name__ == "__main__":
    main()
