"""Vercel serverless entrypoint for the RAG Studio web application."""

from pathlib import Path

from rag_generator.web import make_handler

# Vercel's Python runtime discovers this BaseHTTPRequestHandler subclass by name.
# /tmp is the only writable serverless filesystem location and is intentionally
# treated as an ephemeral cache; generated archives are already built there.
handler = make_handler(Path("/tmp/rag-code-generator.db"))

