import json
import tempfile
import unittest
from pathlib import Path

from dataforger import (
    DatasetConflictError,
    DatasetNotFoundError,
    get_dataset,
    get_or_create_dataset,
    replace_dataset,
)


class DatasetTests(unittest.TestCase):
    def test_create_then_reuse_persisted_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            created = get_or_create_dataset(
                "customers",
                {"id": "uuid", "name": "name"},
                rows=3,
                seed=42,
                directory=directory,
            )
            reused = get_or_create_dataset(
                "customers",
                {"id": "uuid", "name": "name"},
                rows=3,
                seed=42,
                directory=directory,
            )
            loaded = get_dataset("customers", directory)

        self.assertEqual(created, reused)
        self.assertEqual(created, loaded)
        self.assertEqual(len(loaded.data), 3)

    def test_existing_key_rejects_different_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            get_or_create_dataset(
                "customers", {"id": "uuid"}, rows=2, seed=42, directory=directory
            )

            with self.assertRaises(DatasetConflictError):
                get_or_create_dataset(
                    "customers",
                    {"id": "uuid"},
                    rows=3,
                    seed=42,
                    directory=directory,
                )

    def test_replace_updates_saved_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            get_or_create_dataset(
                "customers", {"id": "uuid"}, rows=2, seed=42, directory=directory
            )
            replaced = replace_dataset(
                "customers", {"id": "uuid"}, rows=4, seed=8, directory=directory
            )
            loaded = get_dataset("customers", directory)

        self.assertEqual(replaced, loaded)
        self.assertEqual(loaded.rows, 4)
        self.assertEqual(loaded.seed, 8)

    def test_missing_and_invalid_keys_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DatasetNotFoundError):
                get_dataset("missing", directory)
            with self.assertRaisesRegex(ValueError, "Dataset keys"):
                get_dataset("../outside", directory)

    def test_rejects_boolean_rows_or_seed_even_if_dataset_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            get_or_create_dataset(
                "customers", {"id": "uuid"}, rows=1, seed=1, directory=directory
            )
            with self.assertRaisesRegex(ValueError, "rows must"):
                get_or_create_dataset(
                    "customers", {"id": "uuid"}, rows=True, seed=1, directory=directory
                )
            with self.assertRaisesRegex(ValueError, "seed must"):
                get_or_create_dataset(
                    "customers",
                    {"id": "uuid"},
                    rows=1,
                    seed=True,
                    directory=directory,
                )

    def test_dataset_is_saved_as_json_with_generation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            get_or_create_dataset(
                "customers", {"id": "uuid"}, rows=1, seed=42, directory=directory
            )
            saved = json.loads(
                (Path(directory) / "customers.json").read_text(encoding="utf-8")
            )

        self.assertEqual(saved["key"], "customers")
        self.assertEqual(saved["fields"], {"id": "uuid"})
        self.assertEqual(saved["rows"], 1)
        self.assertEqual(saved["seed"], 42)
        self.assertEqual(saved["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
