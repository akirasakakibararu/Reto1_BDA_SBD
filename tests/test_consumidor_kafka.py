import unittest
from types import SimpleNamespace

from bson.decimal128 import Decimal128

from scripts.kafka.consumidor_anuncios import (
    _listing_document,
    _validate_event,
)


class KafkaConsumerTests(unittest.TestCase):
    def test_validates_and_persists_deserialized_string_key(self) -> None:
        event = {
            "event_id": "test-event-id",
            "event_type": "simulated_rental_listing",
            "is_simulated": True,
            "municipality_code": "20059",
            "municipality_name": "Oñati",
            "monthly_rent_eur": "600",
            "announced_at_utc": "2026-11-16T00:00:00+00:00",
        }
        message = SimpleNamespace(partition=0, offset=4, key="20059")

        document = _listing_document(
            _validate_event(event),
            message,
            "reto_vivienda_test",
        )

        self.assertEqual(document["source"]["key"], "20059")
        self.assertEqual(document["source"]["offset"], 4)
        self.assertEqual(document["listing"]["monthly_rent_eur"], Decimal128("600"))


if __name__ == "__main__":
    unittest.main()
