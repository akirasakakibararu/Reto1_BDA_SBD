import logging
import os

from dotenv import load_dotenv
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

from .configuracion import ROOT, kafka_settings, kafka_topic


def main() -> None:
    load_dotenv(ROOT / ".env")
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
    partitions = int(os.getenv("KAFKA_NUM_PARTITIONS", "1"))
    replication_factor = int(os.getenv("KAFKA_REPLICATION_FACTOR", "1"))
    if partitions < 1 or replication_factor < 1:
        raise ValueError("Particiones y factor de replicación deben ser positivos.")

    admin = None
    try:
        admin = KafkaAdminClient(
            **kafka_settings(),
            client_id="reto-vivienda-admin",
        )
        try:
            admin.create_topics(
                [
                    NewTopic(
                        name=topic,
                        num_partitions=partitions,
                        replication_factor=replication_factor,
                    )
                ]
            )
        except TopicAlreadyExistsError:
            logger.info("El tópico ya existe: %s", topic)
        if topic not in admin.list_topics():
            raise RuntimeError(f"El broker no confirma el tópico {topic}.")
        logger.info("Tópico disponible: %s", topic)
    except KafkaError:
        logger.exception("No se pudo crear o comprobar el tópico %s.", topic)
        raise
    finally:
        if admin is not None:
            admin.close()


if __name__ == "__main__":
    main()
