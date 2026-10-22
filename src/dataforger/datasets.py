import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from dataforger.core import generate_data

_DATASET_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_PROCESS_LOCK = threading.RLock()
_SCHEMA_VERSION = 1


class DatasetConflictError(ValueError):
    """Raised when a dataset key exists with different generation parameters."""


class DatasetNotFoundError(LookupError):
    """Raised when a requested dataset does not exist."""


class DatasetIntegrityError(RuntimeError):
    """Raised when a persisted dataset file is corrupt or unsupported."""


@dataclass(frozen=True)
class Dataset:
    key: str
    fields: dict[str, str]
    rows: int
    seed: int | None
    data: list[dict[str, object]]
    created_at: str


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or _DATASET_KEY.fullmatch(key) is None:
        raise ValueError(
            "Dataset keys must be 1-128 characters using letters, numbers, "
            "dots, underscores, or hyphens, and start with a letter or number."
        )


def _store_directory(directory: str | Path | None) -> Path:
    if directory is not None:
        return Path(directory).expanduser()
    configured_directory = os.environ.get("DATAFORGER_DATA_DIR")
    if configured_directory:
        return Path(configured_directory).expanduser()
    return Path.home() / ".dataforger" / "datasets"


@contextmanager
def _store_lock(directory: Path) -> Generator[None, None, None]:
    directory.mkdir(parents=True, exist_ok=True)
    with _PROCESS_LOCK:
        with (directory / ".dataforger.lock").open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _dataset_path(directory: Path, key: str) -> Path:
    _validate_key(key)
    return directory / f"{key}.json"


def _load_dataset(path: Path, key: str) -> Dataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA_VERSION
            or payload.get("key") != key
            or not isinstance(payload.get("fields"), dict)
            or not isinstance(payload.get("rows"), int)
            or isinstance(payload.get("rows"), bool)
            or payload.get("rows", 0) < 1
            or not isinstance(payload.get("data"), list)
            or not isinstance(payload.get("created_at"), str)
        ):
            raise DatasetIntegrityError(
                f"Dataset {key!r} has invalid or unsupported contents."
            )

        seed = payload.get("seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise DatasetIntegrityError(
                f"Dataset {key!r} has invalid or unsupported contents."
            )
        fields = payload["fields"]
        data = payload["data"]
        if (
            not fields
            or any(
                not isinstance(name, str) or not isinstance(value, str)
                for name, value in fields.items()
            )
            or any(
                not isinstance(record, dict)
                or set(record) != set(fields)
                for record in data
            )
            or payload["rows"] != len(data)
        ):
            raise DatasetIntegrityError(
                f"Dataset {key!r} has invalid or unsupported contents."
            )

        return Dataset(
            key=key,
            fields=fields,
            rows=payload["rows"],
            seed=seed,
            data=data,
            created_at=payload["created_at"],
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise DatasetIntegrityError(
            f"Dataset {key!r} contains invalid JSON."
        ) from error


def _save_dataset(directory: Path, dataset: Dataset) -> None:
    path = _dataset_path(directory, dataset.key)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "key": dataset.key,
        "fields": dataset.fields,
        "rows": dataset.rows,
        "seed": dataset.seed,
        "created_at": dataset.created_at,
        "data": dataset.data,
    }
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=f".{dataset.key}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(payload, temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _generate_dataset(
    key: str,
    fields: Mapping[str, str],
    rows: int,
    seed: int | None,
) -> Dataset:
    _validate_generation_scalars(rows, seed)
    copied_fields = dict(fields)
    data = generate_data(copied_fields, rows=rows, seed=seed)
    return Dataset(
        key=key,
        fields=copied_fields,
        rows=rows,
        seed=seed,
        data=data,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _validate_generation_scalars(rows: int, seed: int | None) -> None:
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1:
        raise ValueError("rows must be a positive integer.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("seed must be an integer or None.")


def get_or_create_dataset(
    key: str,
    fields: Mapping[str, str],
    rows: int = 10,
    seed: int | None = None,
    directory: str | Path | None = None,
) -> Dataset:
    """Return a stored dataset, creating it if its key has not been used."""
    _validate_key(key)
    _validate_generation_scalars(rows, seed)
    root = _store_directory(directory)
    path = _dataset_path(root, key)
    with _store_lock(root):
        if path.exists():
            dataset = _load_dataset(path, key)
            if (
                list(dataset.fields.items()) != list(fields.items())
                or dataset.rows != rows
                or dataset.seed != seed
            ):
                raise DatasetConflictError(
                    f"Dataset {key!r} already exists with different generation "
                    "parameters. Use replace_dataset to replace it."
                )
            return dataset

        dataset = _generate_dataset(key, fields, rows, seed)
        _save_dataset(root, dataset)
        return dataset


def get_dataset(key: str, directory: str | Path | None = None) -> Dataset:
    """Load a dataset by its unique key."""
    _validate_key(key)
    root = _store_directory(directory)
    path = _dataset_path(root, key)
    with _store_lock(root):
        if not path.is_file():
            raise DatasetNotFoundError(f"Dataset {key!r} was not found.")
        return _load_dataset(path, key)


def replace_dataset(
    key: str,
    fields: Mapping[str, str],
    rows: int = 10,
    seed: int | None = None,
    directory: str | Path | None = None,
) -> Dataset:
    """Generate and persist a dataset, replacing any existing dataset at its key."""
    _validate_key(key)
    _validate_generation_scalars(rows, seed)
    root = _store_directory(directory)
    with _store_lock(root):
        dataset = _generate_dataset(key, fields, rows, seed)
        _save_dataset(root, dataset)
        return dataset
