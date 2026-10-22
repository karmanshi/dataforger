import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from dataforger.api import _ApiHandler


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(
        self, method: str, path: str, payload: object | None = None
    ) -> tuple[int, dict[str, object]]:
        connection = http.client.HTTPConnection(self.host, self.port)
        body = None if payload is None else json.dumps(payload)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        return response.status, result

    def test_generate_endpoint_returns_requested_records(self) -> None:
        status, response = self.request(
            "POST",
            "/api/v1/generate",
            {"fields": {"name": "name", "age": "age"}, "rows": 2, "seed": 4},
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["count"], 2)
        self.assertEqual(len(response["data"]), 2)
        self.assertEqual(set(response["data"][0]), {"name", "age"})

    def test_generate_endpoint_reports_invalid_requests(self) -> None:
        status, response = self.request(
            "POST", "/api/v1/generate", {"fields": {"name": "unknown"}}
        )

        self.assertEqual(status, 400)
        self.assertIn("error", response)

    def test_fields_and_health_endpoints(self) -> None:
        health_status, health = self.request("GET", "/health")
        fields_status, fields = self.request("GET", "/api/v1/fields")

        self.assertEqual(health_status, 200)
        self.assertEqual(health, {"status": "ok"})
        self.assertEqual(fields_status, 200)
        self.assertIn("name", fields["fields"])

    def test_unknown_endpoint_returns_not_found(self) -> None:
        status, response = self.request("GET", "/missing")

        self.assertEqual(status, 404)
        self.assertIn("error", response)

    def test_create_get_replace_dataset_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.server.data_directory = directory
            status, created = self.request(
                "POST",
                "/api/v1/datasets",
                {
                    "key": "customers",
                    "fields": {"id": "uuid"},
                    "rows": 2,
                    "seed": 42,
                },
            )
            get_status, loaded = self.request(
                "GET", "/api/v1/datasets/customers"
            )
            replace_status, replaced = self.request(
                "PUT",
                "/api/v1/datasets/customers",
                {"fields": {"id": "uuid"}, "rows": 3, "seed": 8},
            )
            conflict_status, conflict = self.request(
                "POST",
                "/api/v1/datasets",
                {
                    "key": "customers",
                    "fields": {"id": "uuid"},
                    "rows": 2,
                    "seed": 42,
                },
            )

        self.assertEqual(status, 200)
        self.assertEqual(get_status, 200)
        self.assertEqual(created["data"], loaded["data"])
        self.assertEqual(replace_status, 200)
        self.assertEqual(replaced["rows"], 3)
        self.assertEqual(conflict_status, 409)
        self.assertIn("error", conflict)

    def test_get_missing_dataset_returns_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.server.data_directory = directory
            status, response = self.request("GET", "/api/v1/datasets/missing")

        self.assertEqual(status, 404)
        self.assertIn("error", response)


if __name__ == "__main__":
    unittest.main()
