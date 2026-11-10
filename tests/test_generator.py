import json
import runpy
import tempfile
import unittest
from pathlib import Path

from rag_generator.catalog import load_catalog
from rag_generator.generator import generate_repository
from rag_generator.models import Selection


class GeneratorTests(unittest.TestCase):
    def test_repository_contract(self):
        selection = Selection("demo-rag", ("parser.text", "chunker.fixed"), {})
        catalog = load_catalog()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            generate_repository(selection, [catalog[item] for item in selection.components], output)
            self.assertTrue((output / ".env.example").exists())
            self.assertTrue((output / "tests/test_pipeline.py").exists())
            self.assertIn(
                '"demo_rag.app"', (output / "Dockerfile").read_text(encoding="utf-8")
            )
            lock = json.loads((output / "component-lock.json").read_text())
            self.assertEqual(lock["generator_version"], "0.2.0")

    def test_nonempty_output_is_not_overwritten(self):
        selection = Selection("demo", (), {})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "owned.txt").write_text("user data")
            with self.assertRaises(FileExistsError):
                generate_repository(selection, [], output)

    def test_chunking_choice_changes_generated_code(self):
        catalog = load_catalog()
        with tempfile.TemporaryDirectory() as directory:
            sentence = Selection("sentences", ("chunker.sentence",), {})
            recursive = Selection("recursive", ("chunker.recursive",), {})
            first = Path(directory) / "sentence"
            second = Path(directory) / "recursive"
            generate_repository(sentence, [catalog["chunker.sentence"]], first)
            generate_repository(recursive, [catalog["chunker.recursive"]], second)
            self.assertIn('CHUNKING_STYLE = "sentence"', (first / "src/sentences/pipeline.py").read_text())
            self.assertIn('CHUNKING_STYLE = "recursive"', (second / "src/recursive/pipeline.py").read_text())

    def test_openai_embedding_adds_dependency_without_secret(self):
        catalog = load_catalog()
        selection = Selection("openai-demo", ("embedding.openai",), {})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            generate_repository(selection, [catalog["embedding.openai"]], output)
            self.assertIn("openai>=1,<3", (output / "pyproject.toml").read_text())
            self.assertEqual((output / ".env.example").read_text(), "OPENAI_API_KEY=\n")

    def test_pdf_parser_adds_real_adapter(self):
        catalog = load_catalog()
        selection = Selection("pdf-demo", ("parser.pdf",), {})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            generate_repository(selection, [catalog["parser.pdf"]], output)
            self.assertIn("pypdf>=6,<7", (output / "pyproject.toml").read_text())
            self.assertIn("def extract_pdf", (output / "src/pdf_demo/parsers.py").read_text())

    def test_all_structured_parsers_add_adapters_and_dependencies(self):
        catalog = load_catalog()
        parser_ids = ("parser.csv", "parser.excel", "parser.word", "parser.powerpoint")
        selection = Selection("documents", parser_ids, {})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            generate_repository(selection, [catalog[item] for item in parser_ids], output)
            project = (output / "pyproject.toml").read_text()
            source = (output / "src/documents/parsers.py").read_text()
            self.assertIn("openpyxl>=3.1,<4", project)
            self.assertIn("python-docx>=1.1,<2", project)
            self.assertIn("python-pptx>=1.0,<2", project)
            for function in ("extract_csv", "extract_excel", "extract_word", "extract_powerpoint"):
                self.assertIn(f"def {function}", source)
            sample = output / "sample.csv"
            sample.write_text("name,score\nAda,10\nLin,9\n", encoding="utf-8")
            parser_module = runpy.run_path(str(output / "src/documents/parsers.py"))
            text, metadata = parser_module["extract_text"](sample)
            self.assertIn("[Row: 2] name: Ada | score: 10", text)
            self.assertEqual(metadata["rows"], 2)

    def test_async_queue_adds_worker_and_redis(self):
        catalog = load_catalog()
        selection = Selection("queue-demo", ("queue.arq",), {"runtime": "async"})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            generate_repository(selection, [catalog["queue.arq"]], output)
            self.assertIn("arq>=0.26,<1", (output / "pyproject.toml").read_text())
            self.assertIn("redis:", (output / "docker-compose.yml").read_text())
            self.assertIn("class WorkerSettings", (output / "src/queue_demo/worker.py").read_text())
