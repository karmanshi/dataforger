import csv
import json
import random
import uuid
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Callable, Literal

Format = Literal["csv", "json"]

_DATA_KEYS = (
    "first_names",
    "last_names",
    "streets",
    "street_types",
    "companies",
    "company_suffixes",
    "email_domains",
)


def _load_data() -> dict[str, tuple[str, ...]]:
    raw_data = json.loads(
        files("dataforger").joinpath("data.json").read_text(encoding="utf-8")
    )
    if not isinstance(raw_data, dict):
        raise ValueError("Bundled data.json must contain a JSON object.")

    data: dict[str, tuple[str, ...]] = {}
    for key in _DATA_KEYS:
        values = raw_data.get(key)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise ValueError(
                f"Bundled data.json must define {key!r} as a non-empty list "
                "of strings."
            )
        data[key] = tuple(values)
    return data


_DATA = _load_data()


def _load_country_cities() -> dict[str, tuple[str, ...]]:
    raw_data = json.loads(
        files("dataforger").joinpath("countries.json").read_text(encoding="utf-8")
    )
    if not isinstance(raw_data, dict) or not raw_data:
        raise ValueError("Bundled countries.json must contain a non-empty JSON object.")

    country_cities: dict[str, tuple[str, ...]] = {}
    for country, cities in raw_data.items():
        if (
            not isinstance(country, str)
            or not country
            or not isinstance(cities, list)
            or not cities
            or any(not isinstance(city, str) or not city for city in cities)
        ):
            raise ValueError(
                "Bundled countries.json must map country names to non-empty "
                "lists of city names."
            )
        country_cities[country] = tuple(cities)
    return country_cities


_COUNTRY_CITIES = _load_country_cities()

FIELD_TYPES = (
    "name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "city",
    "country",
    "company",
    "uuid",
    "date",
    "age",
    "integer",
    "float",
    "boolean",
)

def _first_name(rng: random.Random) -> str:
    return rng.choice(_DATA["first_names"])


def _last_name(rng: random.Random) -> str:
    return rng.choice(_DATA["last_names"])


def _name(rng: random.Random) -> str:
    return f"{_first_name(rng)} {_last_name(rng)}"


def _email(rng: random.Random) -> str:
    first = _first_name(rng).lower()
    last = _last_name(rng).lower()
    suffix = rng.randint(1, 9999)
    return f"{first}.{last}{suffix}@{rng.choice(_DATA['email_domains'])}"


def _phone(rng: random.Random) -> str:
    area = rng.randint(200, 999)
    exchange = rng.randint(200, 999)
    subscriber = rng.randint(0, 9999)
    return f"+1-{area}-{exchange}-{subscriber:04d}"


def _address(rng: random.Random, city: str) -> str:
    number = rng.randint(1, 9999)
    street = rng.choice(_DATA["streets"])
    street_type = rng.choice(_DATA["street_types"])
    return f"{number} {street} {street_type}, {city}"


def _company(rng: random.Random) -> str:
    company = rng.choice(_DATA["companies"])
    suffix = rng.choice(_DATA["company_suffixes"])
    return f"{company} {suffix}"


def _date(rng: random.Random) -> str:
    start = date(1970, 1, 1)
    days = (date.today() - start).days
    return (start + timedelta(days=rng.randint(0, days))).isoformat()


def _integer(rng: random.Random) -> int:
    return rng.randint(0, 100_000)


def _age(rng: random.Random) -> int:
    return rng.randint(0, 100)


def _float(rng: random.Random) -> float:
    return round(rng.uniform(0, 100_000), 2)


_PROVIDERS: dict[str, Callable[[random.Random], object]] = {
    "name": _name,
    "first_name": _first_name,
    "last_name": _last_name,
    "email": _email,
    "phone": _phone,
    "company": _company,
    "uuid": lambda rng: str(uuid.UUID(int=rng.getrandbits(128), version=4)),
    "date": _date,
    "age": _age,
    "integer": _integer,
    "float": _float,
    "boolean": lambda rng: rng.choice((True, False)),
}


def generate_data(
    fields: Mapping[str, str],
    rows: int = 10,
    seed: int | None = None,
) -> list[dict[str, object]]:
    """Generate records using a mapping of field names to supported value types."""
    if not fields:
        raise ValueError("At least one field is required.")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1:
        raise ValueError("rows must be a positive integer.")

    for name, field_type in fields.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Field names must be non-empty strings.")
        if not isinstance(field_type, str) or field_type not in FIELD_TYPES:
            raise ValueError(
                f"Unknown field type {field_type!r}. Choose from: "
                f"{', '.join(FIELD_TYPES)}."
            )

    rng = random.Random(seed)

    records: list[dict[str, object]] = []
    for _ in range(rows):
        location_country = (
            rng.choice(tuple(_COUNTRY_CITIES))
            if any(
                field_type in ("address", "city", "country")
                for field_type in fields.values()
            )
            else None
        )
        location_city = (
            rng.choice(_COUNTRY_CITIES[location_country])
            if location_country is not None
            and any(field_type in ("address", "city") for field_type in fields.values())
            else None
        )
        record: dict[str, object] = {}
        for name, field_type in fields.items():
            if field_type == "country":
                record[name] = location_country
            elif field_type == "city":
                assert location_city is not None
                record[name] = location_city
            elif field_type == "address":
                assert location_city is not None
                record[name] = _address(rng, location_city)
            else:
                record[name] = _PROVIDERS[field_type](rng)
        records.append(record)
    return records


def write_data(
    records: Sequence[Mapping[str, object]],
    output: str | Path,
    format: Format,
) -> Path:
    """Write generated records to a CSV or JSON file and return its path."""
    if format not in ("csv", "json"):
        raise ValueError("format must be 'csv' or 'json'.")
    if not records:
        raise ValueError("At least one record is required.")

    path = Path(output)
    if format == "json":
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                [dict(record) for record in records],
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")
    else:
        fieldnames = list(records[0])
        if not fieldnames:
            raise ValueError("Records must contain at least one field.")
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
    return path
