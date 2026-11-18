import unittest
from decimal import Decimal

from scripts.extraccion.descargar_api_renta_udalmap import parse_api_response


class ParseUdalmapAPITests(unittest.TestCase):
    def test_extracts_municipal_records_and_leaves_omitted_year_absent(self) -> None:
        payload = {
            "id": "61",
            "name": "Renta personal disponible",
            "municipalities": [
                {
                    "id": "01002",
                    "name": "Amurrio",
                    "years": [{"2023": 20845.0, "2022": 19389.0}],
                },
                {
                    "id": "48916",
                    "name": "Usansolo",
                    "years": [{"2022": 18000.0}],
                },
            ],
        }

        records = parse_api_response(payload)

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["municipality_code"], "01002")
        self.assertEqual(records[0]["year"], 2023)
        self.assertEqual(records[0]["available_income_eur"], Decimal("20845.0"))
        self.assertNotIn(
            ("48916", 2023),
            {(row["municipality_code"], row["year"]) for row in records},
        )

    def test_rejects_wrong_indicator(self) -> None:
        with self.assertRaisesRegex(ValueError, "indicador Udalmap 61"):
            parse_api_response({"id": "162", "municipalities": []})


if __name__ == "__main__":
    unittest.main()
