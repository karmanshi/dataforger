import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dataforger.cli import main


class CliTests(unittest.TestCase):
    def test_generates_requested_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "people.csv"

            with patch(
                "sys.argv",
                [
                    "dataforger",
                    "--rows",
                    "2",
                    "--field",
                    "name:name",
                    "--format",
                    "csv",
                    "--output",
                    str(output),
                    "--seed",
                    "3",
                ],
            ):
                self.assertEqual(main(), 0)

            self.assertTrue(output.exists())
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 3)

    def test_interactive_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "people.json"
            responses = ["2", "json", str(output), "name", "name", ""]

            with patch("builtins.input", side_effect=responses):
                self.assertEqual(main([]), 0)

            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
