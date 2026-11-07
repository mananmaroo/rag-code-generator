from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

from rag_generator.generator import generate_repository
from rag_generator.models import Component, Selection


def repository_zip(selection: Selection, components: list[Component]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="raggen-") as directory:
        root = Path(directory) / "project"
        generate_repository(selection, components, root)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root))
        return buffer.getvalue()


def module_zip(selection: Selection, components: list[Component]) -> bytes:
    full = repository_zip(selection, components)
    source = io.BytesIO(full)
    output = io.BytesIO()
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as outgoing:
        allowed = ("src/", "component-lock.json", ".env.example", "docs/ARCHITECTURE.md")
        for name in incoming.namelist():
            if name.startswith(allowed[0]) or name in allowed[1:]:
                outgoing.writestr(name, incoming.read(name))
    return output.getvalue()
