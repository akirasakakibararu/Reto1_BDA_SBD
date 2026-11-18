import unittest

from scripts.extraccion.descargar_api_indicadores_juventud import (
    parse_filter_ids,
    validate_indicator_response,
)


class YouthIndicatorApiTests(unittest.TestCase):
    def test_filter_ids_are_extracted_from_official_table_markup(self) -> None:
        html = """
        <input name="chkVariable_1" value="1#11"/>
        <input name="chkPeriodo" value="2024-id"/>
        """
        variables, periods = parse_filter_ids(html)
        self.assertEqual(variables, ["1#11"])
        self.assertEqual(periods, ["2024-id"])

    def test_empty_filter_markup_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_filter_ids("<html></html>")

    def test_api_salary_values_are_verified_without_crossing_dimensions(self) -> None:
        labels = {
            "5943": {
                "9266": "Total",
                "9267": "Hombres",
                "9268": "Mujeres",
                "9269": "Álava",
                "9270": "Bizkaia",
                "9271": "Gipuzkoa",
                "9272": "18-29 años",
                "9273": "30-34 años",
            },
            "5944": {"9274": "Salario neto medio mensual"},
        }
        data = {
            f"2024-id#{value_id}#9274": value
            for value_id, value in {
                "9266": "1,564",
                "9267": "1,617",
                "9268": "1,438",
                "9269": "1,487",
                "9270": "1,585",
                "9271": "1,555",
                "9272": "1,381",
                "9273": "1,774",
            }.items()
        }
        payload = {
            "mapaAnios": {"2024-id": "2024"},
            "mapaColumnas": {"1#5943": labels["5943"]},
            "mapaFilas": {"1#5944": {"1_9274": labels["5944"]["9274"]}},
            "mapaDatos": data,
        }
        verified = validate_indicator_response(31, payload)
        self.assertEqual(verified["2024"]["Álava"], "1487")
        self.assertEqual(verified["2024"]["18-29 años"], "1381")

    def test_api_mismatch_is_not_accepted(self) -> None:
        payload = {
            "mapaAnios": {"period": "2024"},
            "mapaColumnas": {
                "1#5943": {"9266": "Total"}
            },
            "mapaFilas": {
                "1#5944": {"1_9274": "Salario neto medio mensual"}
            },
            "mapaDatos": {"period#9266#9274": "1,500"},
        }
        with self.assertRaises(ValueError):
            validate_indicator_response(31, payload)


if __name__ == "__main__":
    unittest.main()
