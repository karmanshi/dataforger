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
| `--format {csv,json}` | Output format; in dataset mode, exports saved records. | `json` |
| `--output PATH` | Path for generated or exported records. | `data.json` or `data.csv`, based on format |
| `--seed INTEGER` | Seed for repeatable output. | Random |
| `--dataset KEY` | Reuse or create a persistent JSON dataset instead of writing an output file. | |
| `--replace-dataset` | Regenerate and replace an existing persistent dataset; requires `--dataset`. | |
| `--data-dir PATH` | Directory for persistent datasets. | `~/.dataforger/datasets` |

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

### Persistent datasets

Persistent datasets let separate CLI runs, Python calls, and REST requests
reuse exactly the same records. Use a unique key for each dataset:

```console
dataforger --dataset customers --field id:uuid --field name:name --rows 100 --seed 42
```

Repeat the same command to load the saved records rather than generating new
ones. By default, a key cannot be reused with different fields, row counts, or
seed; Dataforger reports a conflict instead of silently changing the fixture.
Use `--replace-dataset` to explicitly regenerate it. Dataset keys are limited
to letters, numbers, dots, underscores, and hyphens.
To retrieve a dataset without supplying its generation parameters, omit
`--field`; use `--output` and `--format` to export the saved records:

```console
dataforger --dataset customers --format csv --output customers.csv
```

Datasets are stored as JSON files in `~/.dataforger/datasets` by default. Set
`DATAFORGER_DATA_DIR` to share another location across CLI and Python usage,
or pass `--data-dir PATH` to the CLI. The API server uses the same configured
directory; `dataforger --serve --data-dir PATH` sets it for that server.
Writes are atomic and serialized across threads and processes on the same
machine. For containerized deployments, mount a persistent volume at the
configured directory.

The Python API exposes the same operations:

```python
from dataforger import get_dataset, get_or_create_dataset, replace_dataset

customers = get_or_create_dataset(
    "customers",
    {"id": "uuid", "name": "name"},
    rows=100,
    seed=42,
)
same_customers = get_dataset("customers")
replacement = replace_dataset(
    "customers",
    {"id": "uuid", "name": "name"},
    rows=100,
    seed=43,
)
```

`get_or_create_dataset` returns an existing dataset only when the generation
parameters match. It raises `DatasetConflictError` when they differ and
`DatasetNotFoundError` is raised when `get_dataset` cannot find a key.
`replace_dataset` explicitly generates and stores a replacement. All three
functions accept an optional `directory` argument to override the default
store directory.

## HTTP API

Start the built-in HTTP API with:

```console
dataforger --serve
```

The server listens on `127.0.0.1:8000` by default. Use `--host` and `--port`
to change the bind address and port. The API has no authentication, so keep it
on localhost unless you put it behind an appropriately secured service.

Generate records with a JSON `POST` request to `/api/v1/generate`:

```console
curl -X POST http://127.0.0.1:8000/api/v1/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"fields\":{\"name\":\"name\",\"email\":\"email\",\"age\":\"age\"},\"rows\":2,\"seed\":42}"
```

`fields` is a mapping of output names to supported field types, `rows` is
optional (defaults to `10`, maximum `10000`), and `seed` is optional. The
request body is limited to 1 MiB and `fields` to 100 entries. Responses use
JSON; successful generation returns `{"count": 2, "data": [...]}`, and invalid
requests return a JSON `error` with an appropriate HTTP status.

`GET /api/v1/fields` lists supported field types. `GET /health` returns the
server health status.

Persistent datasets use:

* `POST /api/v1/datasets` with `key`, `fields`, and optional `rows` and `seed`
  to create or reuse a dataset. Reusing the key with different generation
  parameters returns `409 Conflict`.
* `GET /api/v1/datasets/{key}` to retrieve a saved dataset.
* `PUT /api/v1/datasets/{key}` with `fields` and optional `rows` and `seed` to
  explicitly generate or replace the dataset.

These routes use the same JSON file store as the Python and CLI interfaces.
The API has no authentication; keep it bound to localhost unless protected by
an appropriately secured service.
