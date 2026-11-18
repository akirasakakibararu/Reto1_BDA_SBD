import argparse

from .descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://opendata.euskadi.eus/contenidos/estadistica/122417_emal_tablas_estad/"
    "opendata/EMAL.-Barrios-Municipios.-2016-2026_es.xlsx"
)
DESTINO = (
    ROOT
    / "datos"
    / "originales"
    / "alquiler"
    / "emal_alquiler_municipios_2016-2026T1.xlsx"
)
FUENTE = {
    "source": "EMAL - alquiler municipal",
    "publisher": "Gobierno Vasco, Departamento de Vivienda y Agenda Urbana",
    "format": "XLSX original",
    "license": "CC BY 4.0",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga el libro original municipal de alquiler EMAL."
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
