import unittest

from app import app


class VercelConfigurationTests(unittest.TestCase):
    def test_entrypoint_is_fastapi_application(self):
        self.assertEqual(app.title, "RAG Studio")

    def test_required_public_routes_exist(self):
        routes = {route.path for route in app.routes}
        self.assertTrue({"/", "/api/health", "/api/catalog", "/api/validate"} <= routes)

