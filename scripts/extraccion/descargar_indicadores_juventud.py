import argparse

from scripts.extraccion.descarga_comun import ROOT, configurar_logging, descargar_archivo


URL = (
    "https://www.gazteaukera.euskadi.eus/contenidos/noticia/"
    "txostena_panorama_2025/es_def/adjuntos/Indicadores-de-Juventud-2025.pdf"
)
DESTINATION = (
    ROOT
    / "datos"
    / "originales"
    / "juventud"
    / "indicadores_de_juventud_2025.pdf"
)
SOURCE = {
    "source": "Observatorio Vasco de la Juventud",
    "dataset": "Indicadores de Juventud 2025",
    "description": (
        "Indicadores 31 (salario neto juvenil), 32 (renta personal juvenil) "
        "y 49 (coste de acceso al alquiler)"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga el informe oficial de Indicadores de Juventud."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vuelve a descargar el PDF aunque el original local sea válido.",
    )
    args = parser.parse_args()
    configurar_logging()
    metadata = descargar_archivo(
        URL,
        DESTINATION,
        SOURCE,
        forzar=args.force,
    )
    print(
        f"PDF verificado: {metadata['file']} "
        f"(HTTP {metadata['http_status']}, SHA-256 {metadata['sha256']})"
    )


if __name__ == "__main__":
    main()
