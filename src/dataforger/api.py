import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from dataforger.core import FIELD_TYPES, generate_data
from dataforger.datasets import (
    Dataset,
    DatasetConflictError,
    DatasetIntegrityError,
    DatasetNotFoundError,
    get_dataset,
    get_or_create_dataset,
    replace_dataset,
)

MAX_REQUEST_BYTES = 1_048_576
MAX_ROWS = 10_000
MAX_FIELDS = 100
_LOGGER = logging.getLogger(__name__)


class _ApiServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        data_directory: str | Path | None = None,
    ) -> None:
        self.data_directory = data_directory
        super().__init__(address, handler)


class _ApiHandler(BaseHTTPRequestHandler):
    server_version = "DataforgerAPI/1.0"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
        elif path == "/api/v1/fields":
            self._send_json(HTTPStatus.OK, {"fields": list(FIELD_TYPES)})
        elif path.startswith("/api/v1/datasets/"):
            key = unquote(path.removeprefix("/api/v1/datasets/"))
            try:
                dataset = get_dataset(key, getattr(self.server, "data_directory", None))
            except DatasetNotFoundError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            except ValueError as error:
                self._send_error(HTTPStatus.BAD_REQUEST, str(error))
            except DatasetIntegrityError:
                _LOGGER.exception("Persistent dataset failed its integrity check.")
                self._send_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Stored dataset is corrupt or unsupported.",
                )
            except OSError:
                _LOGGER.exception("Unable to read persistent dataset.")
                self._send_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Unable to access dataset storage.",
                )
            else:
                self._send_json(HTTPStatus.OK, _dataset_payload(dataset))
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in ("/api/v1/generate", "/api/v1/datasets"):
            self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        request = self._read_json_request()
        if request is None:
            return

        allowed_properties = {"fields", "rows", "seed"}
        if path == "/api/v1/datasets":
            allowed_properties.add("key")
        unexpected = set(request) - allowed_properties
        if unexpected:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                f"Unexpected request properties: {', '.join(sorted(unexpected))}.",
            )
            return

        try:
            fields, rows, seed = _parse_generation_options(request)
        except ValueError as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
            return

        if path == "/api/v1/generate":
            try:
                records = generate_data(fields, rows=rows, seed=seed)
            except ValueError as error:
                self._send_error(HTTPStatus.BAD_REQUEST, str(error))
                return
            self._send_json(
                HTTPStatus.OK,
                {"count": len(records), "data": records},
            )
            return

        key = request.get("key")
        if not isinstance(key, str):
            self._send_error(HTTPStatus.BAD_REQUEST, "'key' must be a string.")
            return
        try:
            dataset = get_or_create_dataset(
                key, fields, rows, seed, getattr(self.server, "data_directory", None)
            )
        except DatasetConflictError as error:
            self._send_error(HTTPStatus.CONFLICT, str(error))
        except ValueError as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
        except DatasetIntegrityError:
            _LOGGER.exception("Persistent dataset failed its integrity check.")
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Stored dataset is corrupt or unsupported.",
            )
        except OSError:
            _LOGGER.exception("Unable to create or load persistent dataset.")
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to access dataset storage."
            )
        else:
            self._send_json(HTTPStatus.OK, _dataset_payload(dataset))

    def do_PUT(self) -> None:
        path = urlsplit(self.path).path
        prefix = "/api/v1/datasets/"
        if not path.startswith(prefix):
            self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        key = unquote(path.removeprefix(prefix))
        request = self._read_json_request()
        if request is None:
            return
        unexpected = set(request) - {"fields", "rows", "seed"}
        if unexpected:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                f"Unexpected request properties: {', '.join(sorted(unexpected))}.",
            )
            return

        try:
            fields, rows, seed = _parse_generation_options(request)
            dataset = replace_dataset(
                key, fields, rows, seed, getattr(self.server, "data_directory", None)
            )
        except ValueError as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
        except DatasetIntegrityError:
            _LOGGER.exception("Persistent dataset failed its integrity check.")
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Stored dataset is corrupt or unsupported.",
            )
        except OSError:
            _LOGGER.exception("Unable to replace persistent dataset.")
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to access dataset storage."
            )
        else:
            self._send_json(HTTPStatus.OK, _dataset_payload(dataset))

    def _read_json_request(self) -> dict[str, Any] | None:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_error(
                HTTPStatus.LENGTH_REQUIRED, "Content-Length header is required."
            )
            return None

        try:
            body_length = int(content_length)
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.")
            return None

        if body_length < 0:
            self._send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.")
            return None
        if body_length > MAX_REQUEST_BYTES:
            self._send_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large."
            )
            return None

        body = self.rfile.read(body_length)
        if len(body) != body_length:
            self._send_error(HTTPStatus.BAD_REQUEST, "Incomplete request body.")
            return None

        try:
            request: Any = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.")
            return None

        if not isinstance(request, dict):
            self._send_error(
                HTTPStatus.BAD_REQUEST, "Request body must be a JSON object."
            )
            return None
        return request

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _parse_generation_options(
    request: dict[str, Any],
) -> tuple[dict[str, str], int, int | None]:
    fields = request.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("'fields' must be a non-empty JSON object.")
    if len(fields) > MAX_FIELDS:
        raise ValueError(f"'fields' cannot contain more than {MAX_FIELDS} entries.")
    if any(
        not isinstance(name, str) or not isinstance(value, str)
        for name, value in fields.items()
    ):
        raise ValueError("'fields' must map string names to string field types.")

    rows = request.get("rows", 10)
    if (
        isinstance(rows, bool)
        or not isinstance(rows, int)
        or not 1 <= rows <= MAX_ROWS
    ):
        raise ValueError(f"'rows' must be an integer from 1 to {MAX_ROWS}.")

    seed = request.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("'seed' must be an integer or null.")
    return fields, rows, seed


def _dataset_payload(dataset: Dataset) -> dict[str, object]:
    return {
        "key": dataset.key,
        "fields": dataset.fields,
        "rows": dataset.rows,
        "seed": dataset.seed,
        "created_at": dataset.created_at,
        "count": len(dataset.data),
        "data": dataset.data,
    }


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    data_directory: str | Path | None = None,
) -> None:
    """Serve the Dataforger HTTP API until interrupted."""
    if not host:
        raise ValueError("host must not be empty.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 to 65535.")

    server = _ApiServer((host, port), _ApiHandler, data_directory)
    try:
        server.serve_forever()
    finally:
        server.server_close()
