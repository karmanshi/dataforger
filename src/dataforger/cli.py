import argparse
import sys
from collections.abc import Sequence

from dataforger.core import FIELD_TYPES, Format, generate_data, write_data


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
        description="Generate fake data in CSV or JSON format.",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.field:
            fields = _parse_fields(args.field)
            rows = 10 if args.rows is None else args.rows
            output_format: Format = args.format or "json"
            output = args.output or f"data.{output_format}"
        else:
            default_rows = args.rows if args.rows is not None else 10
            rows_input = input(f"Number of rows [{default_rows}]: ").strip()
            rows = int(rows_input) if rows_input else default_rows
            format_input = input(
                f"Output format (csv/json) [{args.format or 'json'}]: "
            ).strip()
            output_format = format_input or args.format or "json"
            output = input(
                f"Output file [{args.output or f'data.{output_format}'}]: "
            ).strip() or args.output or f"data.{output_format}"
            fields = _prompt_fields()

        records = generate_data(fields, rows=rows, seed=args.seed)
        path = write_data(records, output, output_format)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        print("\nGeneration cancelled.", file=sys.stderr)
        return 130

    print(f"Generated {len(records)} rows in {path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
