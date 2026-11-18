import unittest
from decimal import Decimal

from scripts.procesamiento.normalizar_indicadores_juventud import (
    ACCESS_DIMENSIONS,
    SALARY_DIMENSIONS,
    parse_indicator_table,
)
from scripts.mongodb.cargar_indicadores_juveniles import build_salary_documents


class YouthIndicatorPdfTests(unittest.TestCase):
    def test_salary_table_keeps_age_and_territory_margins_separate(self) -> None:
        text = """
        Indicador 31: Salario mensual neto medio
        € 2023 2024
        Total 1.532 1.564
        Álava 1.449 1.487
        18-29 años 1.340 1.381
        30-34 años 1.754 1.774
        """
        dimensions = {
            key: SALARY_DIMENSIONS[key]
            for key in ("total", "alava", "age_18_29", "age_30_34")
        }
        years, rows = parse_indicator_table(text, dimensions)
        self.assertEqual(years, [2023, 2024])
        self.assertEqual(rows["alava"], [Decimal("1449"), Decimal("1487")])
        self.assertEqual(rows["age_18_29"], [Decimal("1340"), Decimal("1381")])

    def test_access_indicator_parses_comma_decimals(self) -> None:
        text = """
        Indicador 49: Coste de acceso
        % 2023 2024
        Total 50,6 52,4
        Álava 49,4 50,2
        18-29 años 57,8 59,4
        """
        dimensions = {
            key: ACCESS_DIMENSIONS[key]
            for key in ("total", "alava", "age_18_29")
        }
        years, rows = parse_indicator_table(text, dimensions)
        self.assertEqual(years, [2023, 2024])
        self.assertEqual(rows["age_18_29"], [Decimal("57.8"), Decimal("59.4")])

    def test_incomplete_published_row_is_rejected(self) -> None:
        text = """
        Indicador 31
        € 2023 2024
        Álava 1.449
        """
        with self.assertRaises(ValueError):
            parse_indicator_table(text, {"alava": SALARY_DIMENSIONS["alava"]})

    def test_salary_documents_do_not_invent_age_by_territory_crosses(self) -> None:
        rows = [
            {
                "indicator_code": "31",
                "year": "2024",
                "geography_level": "territory",
                "territory_code": "01",
                "territory_name": "Álava",
                "age_group": "18-34",
                "sex": "total",
                "net_monthly_salary_eur": "1487",
                "unit": "EUR/month",
                "source_page": "69",
                "source_row": "alava",
            },
            {
                "indicator_code": "31",
                "year": "2024",
                "geography_level": "territory",
                "territory_code": "48",
                "territory_name": "Bizkaia",
                "age_group": "18-34",
                "sex": "total",
                "net_monthly_salary_eur": "1585",
                "unit": "EUR/month",
                "source_page": "69",
                "source_row": "bizkaia",
            },
            {
                "indicator_code": "31",
                "year": "2024",
                "geography_level": "territory",
                "territory_code": "20",
                "territory_name": "Gipuzkoa",
                "age_group": "18-34",
                "sex": "total",
                "net_monthly_salary_eur": "1555",
                "unit": "EUR/month",
                "source_page": "69",
                "source_row": "gipuzkoa",
            },
            {
                "indicator_code": "31",
                "year": "2024",
                "geography_level": "euskadi",
                "territory_code": "",
                "territory_name": "Euskadi",
                "age_group": "18-29",
                "sex": "total",
                "net_monthly_salary_eur": "1381",
                "unit": "EUR/month",
                "source_page": "69",
                "source_row": "age_18_29",
            },
        ]
        metadata = {
            "url": "https://example.test/indicators.pdf",
            "file": "indicators.pdf",
            "sha256": "abc123",
            "downloaded_at_utc": "2026-01-01T00:00:00+00:00",
        }
        documents = build_salary_documents(rows, metadata)
        age_document = next(
            document for document in documents if document["age_group"] == "18-29"
        )
        self.assertIsNone(age_document["territory_code"])
        self.assertEqual(age_document["geography_level"], "euskadi")


if __name__ == "__main__":
    unittest.main()
