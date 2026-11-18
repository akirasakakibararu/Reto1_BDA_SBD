import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from bson.decimal128 import Decimal128
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from scripts.mongodb.mongo_comun import ROOT, mongo_connection
from .configuracion import kafka_group_id, kafka_settings, kafka_topic


CODE_PATTERN = re.compile(r"^\d{5}$")


def _validate_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("El mensaje Kafka debe ser un objeto JSON.")
    required = (
        "event_id",
        "event_type",
        "is_simulated",
        "municipality_code",
        "municipality_name",
        "monthly_rent_eur",
        "announced_at_utc",
    )
    missing = [field for field in required if field not in event]
    if missing:
        raise ValueError(f"Faltan campos obligatorios en el mensaje: {missing}")
    if event["event_type"] != "simulated_rental_listing":
        raise ValueError("Tipo de evento Kafka no admitido.")
    if event["is_simulated"] is not True:
        raise ValueError("Este consumidor solo acepta mensajes marcados como simulados.")
    if not CODE_PATTERN.fullmatch(str(event["municipality_code"])):
        raise ValueError("El código municipal del mensaje no tiene cinco dígitos.")
    if not str(event["municipality_name"]).strip():
        raise ValueError("El nombre municipal del mensaje está vacío.")
    try:
        rent = Decimal(str(event["monthly_rent_eur"]))
    except InvalidOperation as error:
        raise ValueError("El alquiler mensual del mensaje no es numérico.") from error
    if not rent.is_finite() or rent <= 0:
        raise ValueError("El alquiler mensual del mensaje debe ser positivo.")
    return event


def _listing_document(event: dict[str, Any], message: Any, topic: str) -> dict[str, Any]:
    rent = Decimal128(Decimal(str(event["monthly_rent_eur"])))
    listing = {
        "_id": str(event["event_id"]),
        "event_type": event["event_type"],
        "is_simulated": True,
        "municipality_code": event["municipality_code"],
        "municipality_name": event["municipality_name"],
        "listing": {"monthly_rent_eur": rent},
        "announced_at_utc": event["announced_at_utc"],
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "topic": topic,
            "partition": message.partition,
            "offset": message.offset,
            "key": message.key,
        },
    }
    if event.get("surface_m2") is not None:
        listing["listing"]["surface_m2"] = Decimal128(
            Decimal(str(event["surface_m2"]))
        )
    return listing


def main() -> None:
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
    topic = kafka_topic()
    consumer = None
    try:
        consumer = KafkaConsumer(
            topic,
            **kafka_settings(),
            client_id="reto-vivienda-consumidor",
            group_id=kafka_group_id(),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            key_deserializer=lambda value: value.decode("utf-8") if value else None,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )
        with mongo_connection() as (_, database):
            listings = database["anuncios_stream"]
            listings.create_index(
                [("municipality_code", 1), ("announced_at_utc", -1)],
                name="ix_anuncios_municipio_fecha",
            )
            for message in consumer:
                try:
                    event = _validate_event(message.value)
                    document = _listing_document(event, message, topic)
                except (InvalidOperation, TypeError, ValueError):
                    logger.exception(
                        "Mensaje inválido; no se confirma su offset: topic=%s "
                        "partition=%s offset=%s",
                        topic,
                        message.partition,
                        message.offset,
                    )
                    raise
                result = listings.replace_one(
                    {"_id": document["_id"]},
                    document,
                    upsert=True,
                )
                if result.matched_count + (result.upserted_id is not None) != 1:
                    raise RuntimeError(
                        f"No se guardó el mensaje {document['_id']} en MongoDB."
                    )
                consumer.commit()
                logger.info(
                    "Mensaje guardado y offset confirmado: event_id=%s topic=%s "
                    "partition=%s offset=%s",
                    document["_id"],
                    topic,
                    message.partition,
                    message.offset,
                )
    except KafkaError:
        logger.exception("Error del consumidor Kafka.")
        raise
    finally:
        if consumer is not None:
            consumer.close()


if __name__ == "__main__":
    main()
