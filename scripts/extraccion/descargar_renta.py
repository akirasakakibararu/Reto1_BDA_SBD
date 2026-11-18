import argparse

from .descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://opendata.euskadi.eus/contenidos/estadistica/"
    "udalmap_indicador_61/es_def/adjuntos/indicator.csv"
)
DESTINO = (
    ROOT
    / "datos"
    / "originales"
    / "ingresos"
    / "udalmap_renta_personal_disponible.csv"
)
FUENTE = {
    "source": "Udalmap, indicador 61 - renta personal disponible",
    "publisher": "Gobierno Vasco; estadística subyacente de Eustat",
    "format": "CSV original",
    "license": "CC BY 4.0",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga el CSV original de renta personal disponible Udalmap."
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
