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

The `--field` option can be repeated. Supported field types are `name`,
`first_name`, `last_name`, `email`, `phone`, `address`, `city`, `country`,
`company`, `uuid`, `date`, `age`, `integer`, `float`, and `boolean`. If
`--field` is omitted, the command prompts for the row count, format, output
path, and fields. When using command-line field options, the defaults are 10
rows, JSON format, and `data.json`.

## Python API

```python
from dataforger import generate_data, write_data

records = generate_data(
    {"name": "name", "email": "email", "age": "age"},
    rows=100,
    seed=42,
)

write_data(records, "users.json", "json")
write_data(records, "users.csv", "csv")
```

`generate_data` returns a list of dictionaries. Pass the resulting records,
an output path, and either `"csv"` or `"json"` to `write_data`.
