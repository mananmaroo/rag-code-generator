import unittest

from rag_generator.catalog import load_catalog
from rag_generator.compatibility import validate_selection
from rag_generator.models import Selection


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_basic_selection_is_valid(self):
        selection = Selection.from_dict({
            "project_name": "demo",
            "components": ["parser.text", "chunker.fixed", "embedding.hash", "store.pgvector", "retrieval.vector"],
            "settings": {"embedding_dimensions": 1536, "runtime": "sync"},
        })
        self.assertEqual(validate_selection(selection, self.catalog), [])

    def test_dimension_mismatch_is_rejected(self):
        selection = Selection("demo", ("embedding.hash",), {"embedding_dimensions": 3072})
        codes = {issue.code for issue in validate_selection(selection, self.catalog)}
        self.assertIn("dimension_mismatch", codes)

    def test_secret_values_are_rejected(self):
        selection = Selection("demo", (), {"openai_api_key": "should-not-be-here"})
        codes = {issue.code for issue in validate_selection(selection, self.catalog)}
        self.assertIn("secret_value", codes)

    def test_proposed_component_cannot_generate(self):
        selection = Selection("demo", ("parser.pdf",), {})
        codes = {issue.code for issue in validate_selection(selection, self.catalog)}
        self.assertIn("not_implemented", codes)

    def test_empty_selection_is_not_a_complete_repository(self):
        codes = {issue.code for issue in validate_selection(Selection("demo", (), {}), self.catalog)}
        self.assertIn("missing_category", codes)

    def test_invalid_chunk_overlap_is_rejected(self):
        selection = Selection("demo", (), {"chunk_size_words": 100, "chunk_overlap_words": 100})
        codes = {issue.code for issue in validate_selection(selection, self.catalog)}
        self.assertIn("invalid_chunking", codes)
