import argparse
import sys
from collections.abc import Sequence

from dataforger.api import serve
from dataforger.core import FIELD_TYPES, Format, generate_data, write_data
from dataforger.datasets import (
    DatasetIntegrityError,
    DatasetNotFoundError,
    get_dataset,
    get_or_create_dataset,
    replace_dataset,
)


def _parse_fields(values: Sequence[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for value in values:
        name, separator, field_type = value.partition(":")
        name = name.strip()
        field_type = field_type.strip()
        if not separator or not name or not field_type:
            raise ValueError(
                f"Invalid field {value!r}; use the format NAME:TYPE."
            )
        if name in fields:
            raise ValueError(f"Field {name!r} was specified more than once.")
        fields[name] = field_type
    return fields


def _prompt_fields() -> dict[str, str]:
    print(f"Available field types: {', '.join(FIELD_TYPES)}")
    fields: dict[str, str] = {}
    while True:
        name = input("Field name (leave blank when finished): ").strip()
        if not name:
            break
        field_type = input("Field type [name]: ").strip() or "name"
        if name in fields:
            raise ValueError(f"Field {name!r} was specified more than once.")
        fields[name] = field_type
    if not fields:
        raise ValueError("At least one field is required.")
    return fields


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataforger",
        description="Generate, persist, and serve realistic test data.",
    )
    parser.add_argument(
        "--field",
        action="append",
        metavar="NAME:TYPE",
        help="field to generate; repeat for additional fields (e.g. name:name)",
    )
    parser.add_argument("--rows", type=int, help="number of records to generate")
    parser.add_argument(
        "--format",
        choices=("csv", "json"),
        help="output format (defaults to json)",
    )
    parser.add_argument("--output", help="output file path")
    parser.add_argument("--seed", type=int, help="seed for repeatable data")
    parser.add_argument(
        "--dataset",
        metavar="KEY",
        help="persist and reuse a dataset identified by KEY",
    )
    parser.add_argument(
        "--replace-dataset",
        action="store_true",
        help="regenerate and replace the dataset (requires --dataset)",
    )
    parser.add_argument(
        "--data-dir",
        help="directory for persistent datasets (or set DATAFORGER_DATA_DIR)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="run the HTTP API instead of generating a file",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API bind address when using --serve (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port when using --serve (default: 8000)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        if (
            args.field
            or args.rows is not None
            or args.format is not None
            or args.output is not None
            or args.seed is not None
            or args.dataset is not None
            or args.replace_dataset
        ):
            parser.error("--serve cannot be combined with file-generation options.")
        try:
            serve(args.host, args.port, args.data_dir)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        except KeyboardInterrupt:
            print("\nAPI server stopped.", file=sys.stderr)
            return 130
        return 0

    if args.replace_dataset and args.dataset is None:
        parser.error("--replace-dataset requires --dataset.")
    if args.data_dir is not None and args.dataset is None:
        parser.error("--data-dir requires --dataset or --serve.")
    if (
        args.dataset is not None
        and not args.field
        and (args.rows is not None or args.seed is not None or args.replace_dataset)
    ):
        parser.error(
            "Retrieving a dataset by key cannot be combined with --rows, --seed, "
            "or --replace-dataset."
        )

    try:
        if args.dataset is not None and not args.field:
            dataset = get_dataset(args.dataset, directory=args.data_dir)
            if args.output is not None or args.format is not None:
                output_format: Format = args.format or "json"
                output = args.output or f"data.{output_format}"
                path = write_data(dataset.data, output, output_format)
                print(
                    f"Loaded dataset {dataset.key!r} with {dataset.rows} rows "
                    f"into {path}."
                )
            else:
                print(f"Loaded dataset {dataset.key!r} with {dataset.rows} rows.")
            return 0

        if args.field:
            fields = _parse_fields(args.field)
            rows = 10 if args.rows is None else args.rows
            if args.dataset is None:
                output_format = args.format or "json"
                output = args.output or f"data.{output_format}"
        else:
            default_rows = args.rows if args.rows is not None else 10
            if args.dataset is None:
                rows_input = input(f"Number of rows [{default_rows}]: ").strip()
                rows = int(rows_input) if rows_input else default_rows
                format_input = input(
                    f"Output format (csv/json) [{args.format or 'json'}]: "
                ).strip()
                output_format: Format = format_input or args.format or "json"
                output = input(
                    f"Output file [{args.output or f'data.{output_format}'}]: "
                ).strip() or args.output or f"data.{output_format}"
            else:
                rows = default_rows
            fields = _prompt_fields()

        if args.dataset is not None:
            dataset_operation = (
                replace_dataset if args.replace_dataset else get_or_create_dataset
            )
            dataset = dataset_operation(
                args.dataset, fields, rows=rows, seed=args.seed, directory=args.data_dir
            )
            if args.output is not None or args.format is not None:
                output_format = args.format or "json"
                output = args.output or f"data.{output_format}"
                path = write_data(dataset.data, output, output_format)
                print(
                    f"Loaded dataset {dataset.key!r} with {dataset.rows} rows "
                    f"into {path}."
                )
            else:
                print(f"Loaded dataset {dataset.key!r} with {dataset.rows} rows.")
            return 0

        records = generate_data(fields, rows=rows, seed=args.seed)
        path = write_data(records, output, output_format)
    except DatasetNotFoundError as error:
        parser.error(str(error))
    except DatasetIntegrityError as error:
        parser.error(str(error))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        print("\nGeneration cancelled.", file=sys.stderr)
        return 130

    print(f"Generated {len(records)} rows in {path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
