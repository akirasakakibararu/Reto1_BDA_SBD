import unittest
from decimal import Decimal

from scripts.extraccion.scrapear_renta_udalmap import parse_municipality_table


class ParseUdalmapHTMLTests(unittest.TestCase):
    def test_extracts_localized_values_and_decodes_entities(self) -> None:
        html = """
        <table>
          <caption>Detalle por municipios</caption>
          <thead>
            <tr><th>C&oacute;digo municipio</th><th>Municipio</th>
                <th>2023</th><th>2022</th></tr>
          </thead>
          <tbody>
            <tr><td>01002</td><td>Amurrio</td>
                <td>20.845,00</td><td>19.389,00</td></tr>
            <tr><td>48916</td><td>Usansolo</td><td></td><td></td></tr>
          </tbody>
        </table>
        """

        records = parse_municipality_table(html)

        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["municipality_code"], "01002")
        self.assertEqual(records[0]["municipality_name"], "Amurrio")
        self.assertEqual(records[0]["year"], 2023)
        self.assertEqual(records[0]["available_income_eur"], Decimal("20845.00"))
        self.assertIsNone(records[2]["available_income_eur"])

    def test_rejects_html_without_municipality_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "No se encontró"):
            parse_municipality_table("<html><body>No data</body></html>")


if __name__ == "__main__":
    unittest.main()
