from __future__ import annotations

import json
import re
from pathlib import Path

from rag_generator.models import Component, Selection


def generate_repository(
    selection: Selection, components: list[Component], output: Path
) -> list[Path]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    package = _package_name(selection.project_name)
    env_names = sorted({name for item in components for name in item.env})
    lock = {
        "generator_version": "0.2.0",
        "project_name": selection.project_name,
        "components": [{"id": item.id, "version": item.version} for item in components],
        "settings": selection.settings,
    }
    rendered = {
        "README.md": _readme(selection, components, package),
        ".env.example": "\n".join(f"{name}=" for name in env_names) + ("\n" if env_names else ""),
        ".gitignore": ".env\n.venv/\n__pycache__/\n*.pyc\n",
        "component-lock.json": json.dumps(lock, indent=2) + "\n",
        "pyproject.toml": _project_toml(selection, package),
        "Dockerfile": _dockerfile(package),
        "docker-compose.yml": _compose(),
        f"src/{package}/__init__.py": "",
        f"src/{package}/app.py": _app_source(),
        f"src/{package}/pipeline.py": _pipeline_source(selection),
        f"src/{package}/embeddings.py": _embeddings_source(),
        f"src/{package}/retrieval.py": _retrieval_source(),
        "tests/test_pipeline.py": _test_source(package),
        "docs/ARCHITECTURE.md": _generated_architecture(selection, components),
        "eval/README.md": _eval_readme(),
        "eval/cases.jsonl": '{"query":"example question","relevant_chunk_ids":["chunk-1"]}\n',
    }
    paths: list[Path] = []
    for relative, content in rendered.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def _package_name(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not value or value[0].isdigit():
        value = f"rag_{value}"
    return value


def _readme(selection: Selection, components: list[Component], package: str) -> str:
    items = "\n".join(f"- `{item.id}` {item.version}" for item in components)
    return f"""# {selection.project_name}

Generated deterministically by RAG Code Generator 0.2.0.

## Selected components

{items}

## Local demo

```bash
python -m unittest discover -s tests
PYTHONPATH=src python -m {package}.app
```

The demo HTTP service listens on port 8000 and exposes `/health`. Provider secrets belong
in `.env` or a deployment secret manager; never commit them. The generated pipeline is a
safe deterministic scaffold, not a claim that proposed external adapters are installed.
"""


def _project_toml(selection: Selection, package: str) -> str:
    dist = re.sub(r"[^a-zA-Z0-9-]+", "-", selection.project_name).strip("-").lower()
    dependencies = '["openai>=1,<3"]' if "embedding.openai" in selection.components else "[]"
    return f"""[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "{dist}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = {dependencies}

[tool.setuptools.packages.find]
where = ["src"]
include = ["{package}*"]
"""


def _dockerfile(package: str) -> str:
    return f"""FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "{package}.app"]
"""


def _compose() -> str:
    return """services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-local-development-only}
      POSTGRES_DB: rag
    ports: ["5432:5432"]
"""


def _app_source() -> str:
    return '''"""Dependency-free health service; replace with the selected API adapter."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps({"status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
'''


def _pipeline_source(selection: Selection) -> str:
    size = int(selection.settings.get("chunk_size_words", 350))
    overlap = int(selection.settings.get("chunk_overlap_words", 60))
    selected = set(selection.components)
    style = "sentence" if "chunker.sentence" in selected else "recursive" if "chunker.recursive" in selected else "fixed"
    implementation = {
        "fixed": '''    words = normalized.split()
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [" ".join(words[start:start + CHUNK_SIZE]) for start in range(0, len(words), step)]''',
        "sentence": '''    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\\s+", normalized) if item.strip()]
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for sentence in sentences:
        words = sentence.split()
        if current and count + len(words) > CHUNK_SIZE:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(sentence)
        count += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks''',
        "recursive": '''    paragraphs = [item.strip() for item in re.split(r"\\n\\s*\\n", normalized) if item.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        step = CHUNK_SIZE - CHUNK_OVERLAP
        chunks.extend(" ".join(words[start:start + CHUNK_SIZE]) for start in range(0, len(words), step))
    return chunks''',
    }[style]
    return f'''"""Deterministic {style} chunking and authorization primitives."""
import re

CHUNK_SIZE = {size}
CHUNK_OVERLAP = {overlap}
CHUNKING_STYLE = "{style}"


def chunk_text(text: str) -> list[str]:
    normalized = re.sub(r"[ \\t]+", " ", text.replace("\\x00", "")).strip()
    if not normalized:
        return []
    if not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
        raise ValueError("overlap must be smaller than chunk size")
{implementation}


def authorize_tenant(requested_tenant: str, authenticated_tenant: str) -> None:
    """Call before retrieval so unauthorized rows never enter the result set."""
    if requested_tenant != authenticated_tenant:
        raise PermissionError("tenant access denied")
'''


def _test_source(package: str) -> str:
    return f'''import unittest

from {package}.pipeline import authorize_tenant, chunk_text
from {package}.embeddings import HashEmbeddingProvider
from {package}.retrieval import hit_at_k, reciprocal_rank_fusion


class PipelineTests(unittest.TestCase):
    def test_chunking_is_deterministic(self):
        self.assertEqual(chunk_text("one two three"), chunk_text("one two three"))

    def test_tenant_check_fails_closed(self):
        with self.assertRaises(PermissionError):
            authorize_tenant("tenant-a", "tenant-b")

    def test_rrf_combines_rankings(self):
        fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
        self.assertEqual(fused[0][0], "b")

    def test_retrieval_metric(self):
        self.assertEqual(hit_at_k(["a", "b"], {{"b"}}, 2), 1.0)

    def test_hash_embeddings_are_repeatable(self):
        provider = HashEmbeddingProvider(32)
        self.assertEqual(provider.embed_one("same text"), provider.embed_one("same text"))
        self.assertEqual(len(provider.embed_one("same text")), 32)


if __name__ == "__main__":
    unittest.main()
'''


def _embeddings_source() -> str:
    return '''"""Embedding providers. Secrets are read by the caller from its environment."""
import hashlib
import math
import re
from collections.abc import Sequence


class HashEmbeddingProvider:
    """Deterministic plumbing/test provider; not a semantic model."""

    def __init__(self, dimensions: int = 1536) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\\w+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.model, input=list(texts), dimensions=self.dimensions
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
'''


def _retrieval_source() -> str:
    return '''"""Provider-independent rank fusion and retrieval evaluation."""
from collections import defaultdict


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], weights: list[float] | None = None, k: int = 60
) -> list[tuple[str, float]]:
    if k <= 0:
        raise ValueError("k must be positive")
    weights = weights or [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("one weight is required per ranking")
    scores: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(ranked_lists, weights, strict=True):
        for rank, chunk_id in enumerate(ranking, 1):
            scores[chunk_id] += weight / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return float(bool(set(retrieved[:k]) & relevant))


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    return len(set(retrieved[:k]) & relevant) / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, chunk_id in enumerate(retrieved, 1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    import math
    gains = [1.0 if item in relevant else 0.0 for item in retrieved[:k]]
    dcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))
    ideal = sum(1.0 / math.log2(rank + 2) for rank in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def citation(chunk_id: str, source: str, locator: str) -> dict[str, str]:
    return {"chunk_id": chunk_id, "source": source, "locator": locator}
'''


def _generated_architecture(selection: Selection, components: list[Component]) -> str:
    rows = "\n".join(f"| {item.category} | `{item.id}` | {item.tradeoffs} |" for item in components)
    return f"""# Architecture

This project uses a **{selection.settings.get('tier', 'deterministic')}** RAG tier and a
**{selection.settings.get('runtime', 'sync')}** runtime.

| Layer | Component | Trade-offs |
|---|---|---|
{rows}

Secrets are injected at runtime. Tenant authorization must be translated into database
filters before either vector or keyword retrieval. Documents are untrusted input.
"""


def _eval_readme() -> str:
    return """# Evaluation scaffolding

Add labelled queries to `cases.jsonl`. Measure retrieval (Recall@K, MRR, nDCG) separately
from answer quality, store component versions with every run, and gate upgrades on a fixed
regression set before changing production indexes.
"""
