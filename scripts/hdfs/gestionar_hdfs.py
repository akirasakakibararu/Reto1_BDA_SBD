import argparse
import hashlib
import logging
import os
import posixpath
from pathlib import Path, PurePosixPath
from typing import Any

from dotenv import load_dotenv
from hdfs import InsecureClient

from scripts.mongodb.mongo_comun import ROOT


LOCAL_DATA = ROOT / "datos"
SCOPES = ("originales", "procesados")


def _settings() -> tuple[str, str, str]:
    load_dotenv(ROOT / ".env")
    url = os.getenv("HDFS_URL", "").strip()
    user = os.getenv("HDFS_USER", "").strip()
    base_path = os.getenv("HDFS_BASE_PATH", "/reto_vivienda").strip()
    if not url:
        raise ValueError("Configure HDFS_URL en el archivo .env.")
    if not base_path.startswith("/") or ".." in PurePosixPath(base_path).parts:
        raise ValueError("HDFS_BASE_PATH debe ser una ruta absoluta sin '..'.")
    return url, user, base_path.rstrip("/")


def _client() -> tuple[InsecureClient, str]:
    url, user, base_path = _settings()
    return InsecureClient(url, user=user or None), base_path


def _remote_path(base_path: str, relative_path: str) -> str:
    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("La ruta remota debe ser relativa a HDFS_BASE_PATH.")
    return posixpath.join(base_path, candidate.as_posix())


def _sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_remote(client: InsecureClient, remote_path: str) -> str:
    digest = hashlib.sha256()
    with client.read(remote_path, chunk_size=1024 * 1024) as source:
        for chunk in source:
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(
    client: InsecureClient, local_path: Path, remote_path: str
) -> dict[str, Any]:
    local_size = local_path.stat().st_size
    remote_status = client.status(remote_path)
    if remote_status["type"] != "FILE":
        raise ValueError(f"La ruta remota no es un archivo: {remote_path}")
    if int(remote_status["length"]) != local_size:
        raise ValueError(
            f"Tamaño distinto para {remote_path}: local={local_size}, "
            f"HDFS={remote_status['length']}"
        )
    local_hash = _sha256_local(local_path)
    remote_hash = _sha256_remote(client, remote_path)
    if local_hash != remote_hash:
        raise ValueError(f"SHA-256 distinto tras la transferencia: {remote_path}")
    return {
        "local_file": str(local_path.relative_to(ROOT)),
        "remote_file": remote_path,
        "size_bytes": local_size,
        "sha256": local_hash,
        "verified": True,
    }


def _initialize(client: InsecureClient, base_path: str) -> None:
    for scope in SCOPES:
        client.makedirs(posixpath.join(base_path, scope))
    logging.info("Directorios base preparados bajo %s", base_path)


def _upload(
    client: InsecureClient, base_path: str, scope: str
) -> list[dict[str, Any]]:
    if scope not in SCOPES:
        raise ValueError(f"Ámbito de carga no admitido: {scope}")
    local_root = LOCAL_DATA / scope
    if not local_root.is_dir():
        raise FileNotFoundError(f"No existe la carpeta local: {local_root}")
    remote_root = posixpath.join(base_path, scope)
    client.makedirs(remote_root)
    files = sorted(path for path in local_root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"No hay archivos para subir desde {local_root}")

    results = []
    for local_path in files:
        relative = local_path.relative_to(local_root).as_posix()
        remote_path = posixpath.join(remote_root, relative)
        client.makedirs(posixpath.dirname(remote_path))
        client.upload(remote_path, str(local_path), overwrite=True)
        results.append(_verify_file(client, local_path, remote_path))
    return results


def _list_recursive(client: InsecureClient, remote_path: str) -> list[dict[str, Any]]:
    results = []
    for name in client.list(remote_path):
        child = posixpath.join(remote_path, name)
        status = client.status(child)
        results.append(
            {
                "path": child,
                "type": status["type"],
                "length": int(status["length"]),
            }
        )
        if status["type"] == "DIRECTORY":
            results.extend(_list_recursive(client, child))
    return results


def _download(
    client: InsecureClient,
    base_path: str,
    remote_relative_path: str,
    destination_relative_path: str | None,
) -> dict[str, Any]:
    remote_path = _remote_path(base_path, remote_relative_path)
    relative_destination = destination_relative_path or (
        f"datos/recuperados/{PurePosixPath(remote_relative_path).name}"
    )
    destination = (ROOT / relative_destination).resolve()
    if not destination.is_relative_to(ROOT.resolve()):
        raise ValueError("El archivo recuperado debe permanecer dentro del proyecto.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    client.download(remote_path, str(destination), overwrite=True)
    return _verify_file(client, destination, remote_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara y administra archivos del proyecto en WebHDFS."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Crea originales/ y procesados/ en HDFS.")
    upload_parser = subparsers.add_parser(
        "upload", help="Sube archivos y verifica su hash."
    )
    upload_parser.add_argument("--scope", choices=(*SCOPES, "ambos"), required=True)
    subparsers.add_parser("list", help="Lista recursivamente el árbol remoto.")
    download_parser = subparsers.add_parser(
        "download", help="Recupera un archivo remoto."
    )
    download_parser.add_argument("--remote-relative-path", required=True)
    download_parser.add_argument("--destination")
    verify_parser = subparsers.add_parser(
        "verify", help="Compara tamaño y SHA-256 local/remoto."
    )
    verify_parser.add_argument("--local-file", required=True)
    verify_parser.add_argument("--remote-relative-path", required=True)
    args = parser.parse_args()

    log_path = ROOT / "logs" / "hdfs.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    client, base_path = _client()
    if args.command == "init":
        _initialize(client, base_path)
    elif args.command == "upload":
        scopes = SCOPES if args.scope == "ambos" else (args.scope,)
        for scope in scopes:
            for result in _upload(client, base_path, scope):
                logging.info("Archivo verificado: %s", result)
    elif args.command == "list":
        for result in _list_recursive(client, base_path):
            logging.info("%s", result)
    elif args.command == "download":
        result = _download(
            client,
            base_path,
            args.remote_relative_path,
            args.destination,
        )
        logging.info("Recuperación verificada: %s", result)
    elif args.command == "verify":
        local_path = (ROOT / args.local_file).resolve()
        if not local_path.is_relative_to(ROOT.resolve()) or not local_path.is_file():
            raise FileNotFoundError(
                "El archivo local debe existir dentro del proyecto."
            )
        remote_path = _remote_path(base_path, args.remote_relative_path)
        logging.info("%s", _verify_file(client, local_path, remote_path))


if __name__ == "__main__":
    main()
