import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dataforger.cli import main


class CliTests(unittest.TestCase):
    def test_starts_http_api_with_requested_address(self) -> None:
        with patch("dataforger.cli.serve") as api_server:
            self.assertEqual(
                main(["--serve", "--host", "127.0.0.2", "--port", "8123"]),
                0,
            )

        api_server.assert_called_once_with("127.0.0.2", 8123, None)

    def test_persistent_dataset_reuses_records_between_cli_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            arguments = [
                "--dataset",
                "customers",
                "--data-dir",
                directory,
                "--rows",
                "2",
                "--field",
                "id:uuid",
                "--seed",
                "4",
            ]
            self.assertEqual(main(arguments), 0)
            saved_records = (Path(directory) / "customers.json").read_text(
                encoding="utf-8"
            )
            self.assertEqual(main(arguments), 0)
            self.assertEqual(
                (Path(directory) / "customers.json").read_text(encoding="utf-8"),
                saved_records,
            )
            output = Path(directory) / "export.csv"
            self.assertEqual(
                main(
                    [
                        "--dataset",
                        "customers",
                        "--data-dir",
                        directory,
                        "--format",
                        "csv",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 3)

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
