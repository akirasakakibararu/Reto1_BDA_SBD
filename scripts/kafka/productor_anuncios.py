import argparse
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

from .configuracion import ROOT, kafka_settings, kafka_topic


CODE_PATTERN = re.compile(r"^\d{5}$")


def _decimal_argument(value: str, argument_name: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError(
            f"{argument_name} debe ser un número decimal."
        ) from error
    if not number.is_finite() or number <= 0:
        raise argparse.ArgumentTypeError(f"{argument_name} debe ser mayor que cero.")
    return format(number, "f")


def _build_event(args: argparse.Namespace) -> dict[str, Any]:
    code = args.municipality_code.strip()
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("El código municipal debe tener cinco dígitos.")
    name = args.municipality_name.strip()
    if not name:
        raise ValueError("El nombre municipal no puede estar vacío.")
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "simulated_rental_listing",
        "is_simulated": True,
        "municipality_code": code,
        "municipality_name": name,
        "monthly_rent_eur": args.monthly_rent_eur,
        "announced_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "command_line_simulator",
    }
    if args.surface_m2:
        event["surface_m2"] = args.surface_m2
    return event


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envía un anuncio inmobiliario explícitamente simulado a Kafka."
    )
    parser.add_argument("--municipality-code", required=True)
    parser.add_argument("--municipality-name", required=True)
    parser.add_argument(
        "--monthly-rent-eur",
        required=True,
        type=lambda value: _decimal_argument(value, "--monthly-rent-eur"),
    )
    parser.add_argument(
        "--surface-m2",
        type=lambda value: _decimal_argument(value, "--surface-m2"),
    )
    args = parser.parse_args()

    log_path = ROOT / "logs" / "kafka.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("reto_vivienda.kafka")
    event = _build_event(args)
    producer = None
    try:
        producer = KafkaProducer(
            **kafka_settings(),
            client_id="reto-vivienda-productor",
            key_serializer=lambda key: key.encode("utf-8"),
            value_serializer=lambda value: json.dumps(
                value, ensure_ascii=False
            ).encode("utf-8"),
        )
        metadata = producer.send(
            kafka_topic(),
            key=event["municipality_code"],
            value=event,
        ).get(timeout=30)
        logger.info(
            "Mensaje simulado confirmado: topic=%s partition=%s offset=%s event_id=%s",
            metadata.topic,
            metadata.partition,
            metadata.offset,
            event["event_id"],
        )
    except KafkaError:
        logger.exception("No se pudo enviar el anuncio simulado.")
        raise
    finally:
        if producer is not None:
            producer.close(timeout=10)


if __name__ == "__main__":
    main()
