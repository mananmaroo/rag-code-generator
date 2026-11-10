import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from rag_generator.web import make_handler


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(Path(cls.temp.name) / "test.db")
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers, response.read()

    def selection(self):
        return {
            "project_name": "web-demo",
            "components": ["parser.text", "chunker.fixed", "embedding.hash", "store.pgvector", "retrieval.vector"],
            "settings": {"runtime": "sync", "embedding_dimensions": 1536},
        }

    def test_catalog_and_ui(self):
        _, _, page = self.request("/")
        self.assertIn(b"RAG Studio", page)
        self.assertIn(b"Your RAG pipeline", page)
        self.assertIn(b"Document parsing", page)
        self.assertIn(b"Coming soon", page)
        self.assertIn(b"Provider credentials", page)
        self.assertIn(b"Browser-local only", page)
        self.assertIn(b"Learn about", page)
        _, _, body = self.request("/api/catalog")
        self.assertGreater(len(json.loads(body)["components"]), 5)

    def test_validate_generate_and_archive_contract(self):
        _, _, body = self.request("/api/validate", self.selection())
        self.assertTrue(json.loads(body)["valid"])
        _, headers, archive = self.request("/api/generate/repository", self.selection())
        self.assertEqual(headers.get_content_type(), "application/zip")
        with zipfile.ZipFile(io.BytesIO(archive)) as result:
            names = set(result.namelist())
            self.assertIn("component-lock.json", names)
            self.assertIn("tests/test_pipeline.py", names)
            combined = b"".join(result.read(name) for name in names)
            self.assertNotIn(b"should-not-be-here", combined)

    def test_invalid_configuration_cannot_generate(self):
        bad = self.selection()
        bad["settings"]["embedding_dimensions"] = 999
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/generate/repository", bad)
        self.assertEqual(raised.exception.code, 422)

    def test_saved_configuration_lifecycle(self):
        _, _, body = self.request("/api/configurations", {"name": "Saved", "selection": self.selection()})
        identifier = json.loads(body)["id"]
        _, _, saved = self.request(f"/api/configurations/{identifier}")
        self.assertEqual(json.loads(saved)["name"], "Saved")
