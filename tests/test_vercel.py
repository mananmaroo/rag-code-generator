import json
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from api.index import handler


class VercelConfigurationTests(unittest.TestCase):
    def test_entrypoint_is_http_handler(self):
        self.assertTrue(issubclass(handler, BaseHTTPRequestHandler))

    def test_all_routes_reach_serverless_entrypoint(self):
        config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["rewrites"][0]["destination"], "/api/index.py")

