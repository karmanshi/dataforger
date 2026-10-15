import csv
import json
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from dataforger import FIELD_TYPES, generate_data, write_data


class GenerateDataTests(unittest.TestCase):
    def test_bundled_data_file_contains_raw_values_used_by_generators(self) -> None:
        data = json.loads(
            files("dataforger").joinpath("data.json").read_text(encoding="utf-8")
        )
        country_cities = json.loads(
            files("dataforger")
            .joinpath("countries.json")
            .read_text(encoding="utf-8")
        )
        records = generate_data(
            {"name": "name", "city": "city", "country": "country"},
            rows=20,
            seed=10,
        )

        self.assertIn(records[0]["name"].split()[0], data["first_names"])
        self.assertIn(records[0]["name"].split()[1], data["last_names"])
        self.assertTrue(all(record["country"] in country_cities for record in records))
        self.assertTrue(
            all(
                record["city"] in country_cities[record["country"]]
                for record in records
            )
        )

    def test_address_city_matches_generated_country(self) -> None:
        country_cities = json.loads(
            files("dataforger")
            .joinpath("countries.json")
            .read_text(encoding="utf-8")
        )
        records = generate_data(
            {"country": "country", "city": "city", "address": "address"},
            rows=20,
            seed=20,
        )

        for record in records:
            self.assertIn(record["city"], country_cities[record["country"]])
            self.assertIn(record["city"], record["address"])

    def test_generates_requested_fields_and_row_count(self) -> None:
        records = generate_data(
            {
                "full_name": "name",
                "age": "age",
                "score": "integer",
                "active": "boolean",
            },
            rows=3,
            seed=10,
        )

        self.assertEqual(len(records), 3)
        self.assertEqual(set(records[0]), {"full_name", "age", "score", "active"})
        self.assertTrue(all(0 <= record["age"] <= 100 for record in records))
        self.assertTrue(all(isinstance(record["score"], int) for record in records))
        self.assertTrue(all(isinstance(record["active"], bool) for record in records))

    def test_seed_repeats_output(self) -> None:
        fields = {"name": "name", "email": "email"}

        self.assertEqual(
            generate_data(fields, rows=2, seed=7),
            generate_data(fields, rows=2, seed=7),
        )

    def test_rejects_empty_fields_invalid_type_and_row_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one field"):
            generate_data({})
        with self.assertRaisesRegex(ValueError, "Unknown field type"):
            generate_data({"value": "not-a-type"})
        with self.assertRaisesRegex(ValueError, "positive integer"):
            generate_data({"name": "name"}, rows=0)
        self.assertIn("email", FIELD_TYPES)


class WriteDataTests(unittest.TestCase):
    def test_writes_json_and_csv(self) -> None:
        records = [{"name": "Ada", "age": 37}, {"name": "Lin", "age": 28}]
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "records.json"
            csv_path = Path(directory) / "records.csv"

            self.assertEqual(write_data(records, json_path, "json"), json_path)
            self.assertEqual(write_data(records, csv_path, "csv"), csv_path)

            with json_path.open(encoding="utf-8") as file:
                self.assertEqual(json.load(file), records)
            with csv_path.open(encoding="utf-8", newline="") as file:
                self.assertEqual(
                    list(csv.DictReader(file)),
                    [{"name": "Ada", "age": "37"}, {"name": "Lin", "age": "28"}],
                )

    def test_rejects_empty_records_and_unknown_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one record"):
            write_data([], "empty.json", "json")
        with self.assertRaisesRegex(ValueError, "format must"):
            write_data([{"name": "Ada"}], "records.xml", "xml")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
