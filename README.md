# RAG Code Generator

An à-la-carte, compatibility-aware generator for production-shaped RAG projects.
Users select capabilities from a catalogue; the generator validates the selection and
renders reviewed templates rather than asking an LLM to invent a repository.

## What is implemented now

- A versioned JSON component catalogue with typed loading.
- Compatibility rules for required capabilities, conflicting selections, embedding
  dimensions, sync/async modes, and hybrid retrieval dependencies.
- A deterministic CLI that can list, validate, and generate a runnable starter repository.
- Generated security defaults: `.env.example`, no embedded secrets, tenant-aware API
  request models, Docker setup, tests, architecture notes, and evaluation scaffolding.

This first slice proves the generator architecture. It does **not** yet claim that every
catalogue entry has a full production adapter. See [the roadmap](docs/ROADMAP.md).

## Try it

```bash
python -m rag_generator.cli catalog
python -m rag_generator.cli validate examples/basic.json
python -m rag_generator.cli generate examples/basic.json --output ./generated/basic-rag
cd generated/basic-rag
python -m unittest discover -s tests
```

Start the visual configurator:

```bash
python -m rag_generator.cli serve
```

Then open `http://127.0.0.1:8080`. Configurations are saved locally in SQLite and
downloads are built in temporary directories before being returned as ZIP files.

The product and generated service use only the Python standard library for their local
deterministic paths. Their manifests record selected production integration points.

## Design boundary

The separate learning project at `complex-rag-system` informed the ingestion/retrieval
model, extractor choices, RRF rules, and evaluation approach. No files are imported from
or written back to that repository.
