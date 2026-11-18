import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def kafka_settings() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    bootstrap_servers = [
        server.strip()
        for server in os.getenv("KAFKA_BOOTSTRAP_SERVERS", "").split(",")
        if server.strip()
    ]
    if not bootstrap_servers:
        raise ValueError("Configure KAFKA_BOOTSTRAP_SERVERS en el archivo .env.")

    security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip()
    if not security_protocol:
        raise ValueError("KAFKA_SECURITY_PROTOCOL no puede estar vacío.")
    settings: dict[str, Any] = {
        "bootstrap_servers": bootstrap_servers,
        "security_protocol": security_protocol,
    }

    sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM", "").strip()
    username = os.getenv("KAFKA_SASL_USERNAME", "").strip()
    password = os.getenv("KAFKA_SASL_PASSWORD", "")
    uses_sasl = security_protocol.upper().startswith("SASL_")
    if uses_sasl:
        if not sasl_mechanism or not username or not password:
            raise ValueError(
                "SASL requiere KAFKA_SASL_MECHANISM, "
                "KAFKA_SASL_USERNAME y KAFKA_SASL_PASSWORD."
            )
        settings.update(
            {
                "sasl_mechanism": sasl_mechanism,
                "sasl_plain_username": username,
                "sasl_plain_password": password,
            }
        )
    elif sasl_mechanism or username or password:
        raise ValueError(
            "Hay parámetros SASL definidos, pero KAFKA_SECURITY_PROTOCOL "
            "no es SASL_PLAINTEXT ni SASL_SSL."
        )

    ca_location = os.getenv("KAFKA_SSL_CA_LOCATION", "").strip()
    if ca_location:
        if "SSL" not in security_protocol.upper():
            raise ValueError(
                "KAFKA_SSL_CA_LOCATION solo se usa con un protocolo SSL."
            )
        settings["ssl_cafile"] = ca_location
    return settings


def kafka_topic() -> str:
    load_dotenv(ROOT / ".env")
    topic = os.getenv("KAFKA_TOPIC", "anuncios_vivienda").strip()
    if not topic:
        raise ValueError("KAFKA_TOPIC no puede estar vacío.")
    return topic


def kafka_group_id() -> str:
    load_dotenv(ROOT / ".env")
    group_id = os.getenv("KAFKA_GROUP_ID", "consumidor_anuncios_mongodb").strip()
    if not group_id:
        raise ValueError("KAFKA_GROUP_ID no puede estar vacío.")
    return group_id
