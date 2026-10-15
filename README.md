# dataforger

Generate realistic fake data from Python or the command line, and save it as
CSV or JSON. Dataforger uses only the Python standard library and has no
third-party runtime dependencies.

Built-in names, streets, companies, and email domains are stored in
`src/dataforger/data.json`. Country names and their associated cities are
stored in `src/dataforger/countries.json`; when generating a record with both
country and city fields, the city is selected from that country's list.

## Install

Requires Python 3.10 or later.

From a checkout of this repository:

```console
python -m pip install .
```

After publishing the package to PyPI:

```console
python -m pip install dataforger
```

## Publishing to PyPI

The GitHub Actions workflow runs the tests on Python 3.10 through 3.13 and
builds wheel and source distributions on pushes and pull requests. To publish,
configure a PyPI trusted publisher for this GitHub repository, using workflow
`.github/workflows/publish.yml` and the GitHub environment `pypi`. Then create
and publish a GitHub Release; the workflow publishes its tested distributions
to PyPI using trusted publishing.

## Command line

Run `dataforger` without field options for an interactive prompt. Or specify
all options directly:

```console
dataforger --rows 100 --field name:name --field email:email --field age:age --format csv --output users.csv --seed 42
```

### CLI options

| Option | Description | Default |
| --- | --- | --- |
| `--field NAME:TYPE` | Output column name and the type of value to generate. Repeat to add fields. | Prompts for fields if omitted |
| `--rows COUNT` | Number of records. Must be a positive integer. | `10` |
| `--format {csv,json}` | Output file format. | `json` |
| `--output PATH` | Path to the output file. | `data.json` or `data.csv`, based on format |
| `--seed INTEGER` | Seed for repeatable output. | Random |

`NAME` is the column/key to write in the output; choose any non-empty name.
`TYPE` must be one of the supported field types below. For example,
`--field first_name:first_name` creates a column named `first_name` using
generated first names, while `--field given:first_name` creates the same kind
of values under the column name `given`.

### Supported field types

| Type | Generated value |
| --- | --- |
| `name` | Full name |
| `first_name` | First name |
| `last_name` | Last name |
| `email` | Email address using a reserved example domain |
| `phone` | Phone-like number |
| `address` | Street address including a generated city |
| `city` | City from the bundled country-to-city data |
| `country` | Country from the bundled country-to-city data |
| `company` | Company name |
| `uuid` | UUID |
| `date` | Date between 1970-01-01 and today |
| `age` | Integer from 0 to 100 |
| `integer` | Integer from 0 to 100,000 |
| `float` | Decimal value from 0 to 100,000 |
| `boolean` | `true` or `false` |

When a record requests both `country` and `city`, the city is selected from
that country's city list. If it also requests `address`, its city matches
those fields.

## Python API

```python
from dataforger import generate_data, write_data

records = generate_data(
    {
        "first_name": "first_name",
        "last_name": "last_name",
        "country": "country",
        "city": "city",
        "email": "email",
        "age": "age",
    },
    rows=100,
    seed=42,
)

write_data(records, "users.json", "json")
write_data(records, "users.csv", "csv")
```

`generate_data` returns a list of dictionaries. Pass the resulting records,
an output path, and either `"csv"` or `"json"` to `write_data`.
Its parameters are `fields` (a mapping of output column names to supported
types), `rows` (positive record count), and optional `seed` (integer for
repeatable values). `write_data` takes `records`, `output` (path), and
`format` (`"csv"` or `"json"`).
