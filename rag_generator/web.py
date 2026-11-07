from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from rag_generator.archive import module_zip, repository_zip
from rag_generator.catalog import load_catalog
from rag_generator.compatibility import validate_selection
from rag_generator.models import Selection
from rag_generator.store import ConfigurationStore

MAX_REQUEST_BYTES = 1_000_000


def component_payload(item):
    return {
        "id": item.id, "version": item.version, "category": item.category,
        "name": item.name, "description": item.description, "status": item.status,
        "provides": list(item.provides), "requires": list(item.requires),
        "runtime": item.runtime, "embedding_dimensions": list(item.embedding_dimensions),
        "tradeoffs": item.tradeoffs, "env": list(item.env),
    }


def make_handler(database: Path):
    catalog = load_catalog()
    store = ConfigurationStore(database)

    class Handler(BaseHTTPRequestHandler):
        server_version = "RAGGenerator/0.2"

        def log_message(self, format: str, *args) -> None:
            if os.environ.get("RAGGEN_ACCESS_LOG") == "1":
                super().log_message(format, *args)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, UI.encode(), "text/html; charset=utf-8")
            elif path == "/api/health":
                self._json(200, {"status": "ok", "catalog_components": len(catalog)})
            elif path == "/api/catalog":
                self._json(200, {"components": [component_payload(item) for item in catalog.values()]})
            elif path == "/api/configurations":
                self._json(200, {"configurations": store.list()})
            elif path.startswith("/api/configurations/"):
                identifier = path.rsplit("/", 1)[-1]
                value = store.get(identifier)
                self._json(200, value) if value else self._json(404, {"error": "not_found"})
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self._body()
                if path == "/api/validate":
                    selection = Selection.from_dict(body)
                    issues = validate_selection(selection, catalog)
                    self._json(200, {"valid": not issues, "issues": [issue.__dict__ for issue in issues]})
                elif path == "/api/configurations":
                    selection = Selection.from_dict(body["selection"])
                    issues = validate_selection(selection, catalog, require_implemented=False)
                    if issues:
                        self._json(422, {"error": "invalid_selection", "issues": [i.__dict__ for i in issues]})
                        return
                    identifier = store.save(str(body.get("name") or selection.project_name), body["selection"], body.get("id"))
                    self._json(201, {"id": identifier})
                elif path in {"/api/generate/repository", "/api/generate/module"}:
                    selection = Selection.from_dict(body)
                    issues = validate_selection(selection, catalog)
                    if issues:
                        self._json(422, {"error": "invalid_selection", "issues": [i.__dict__ for i in issues]})
                        return
                    components = [catalog[item] for item in selection.components]
                    content = repository_zip(selection, components) if path.endswith("repository") else module_zip(selection, components)
                    self._send(200, content, "application/zip", {"Content-Disposition": 'attachment; filename="rag-project.zip"'})
                else:
                    self._json(404, {"error": "not_found"})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(400, {"error": "bad_request", "detail": str(exc)})

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            if path.startswith("/api/configurations/"):
                identifier = path.rsplit("/", 1)[-1]
                self._json(200, {"deleted": True}) if store.delete(identifier) else self._json(404, {"error": "not_found"})
            else:
                self._json(404, {"error": "not_found"})

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_REQUEST_BYTES:
                raise ValueError("request_too_large")
            raw = self.rfile.read(length)
            value = json.loads(raw or b"{}")
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            return value

        def _json(self, status: int, value) -> None:
            self._send(status, json.dumps(value).encode(), "application/json")

        def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080, database: Path = Path("work/raggen.db")) -> None:
    print(f"RAG Code Generator running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), make_handler(database)).serve_forever()


UI = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Code Generator</title><style>
:root{font-family:Inter,system-ui,sans-serif;color:#19221b;background:#f4f7f2}body{margin:0}header{padding:28px;background:#173f2a;color:white}main{max-width:1100px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:white;border:1px solid #d9e2da;border-radius:12px;padding:16px}.card.proposed{opacity:.62}label{display:block;margin:8px 0}input,select,button{font:inherit;padding:9px;border-radius:8px;border:1px solid #9aaa9d}button{background:#17643a;color:white;cursor:pointer;margin:5px}.bar{position:sticky;bottom:0;background:#eef4ef;padding:14px;border-top:1px solid #ccd8ce}#status{white-space:pre-wrap}.tag{font-size:12px;background:#e2eee5;padding:3px 7px;border-radius:10px}</style></head>
<body><header><h1>RAG Code Generator</h1><p>Choose compatible capabilities. Generate reviewed code, not mystery code.</p></header>
<main><label>Project name <input id="name" value="my-rag-service"></label><label>Embedding dimensions <select id="dims"><option>1536</option><option>768</option><option>384</option></select></label><div id="catalog" class="grid"></div></main>
<div class="bar"><button onclick="validate()">Validate</button><button onclick="download('module')">Download modules</button><button onclick="download('repository')">Download repository</button><button onclick="save()">Save configuration</button><span id="status"></span></div>
<script>
let components=[];const chosen=new Set();
async function init(){components=(await (await fetch('/api/catalog')).json()).components;const single=new Set(['chunker','embedding','vector_store','retrieval']);document.querySelector('#catalog').innerHTML=components.map(c=>`<section class="card ${c.status}"><label><input type="${single.has(c.category)?'radio':'checkbox'}" name="${single.has(c.category)?c.category:c.id}" ${c.status==='proposed'?'disabled':''} onchange="choose('${c.id}','${c.category}',this.checked)"> <b>${c.name}</b></label><span class="tag">${c.category} · ${c.status}</span><p>${c.description}</p><small>${c.tradeoffs}</small></section>`).join('')}
function choose(id,category,on){if(['chunker','embedding','vector_store','retrieval'].includes(category))components.filter(c=>c.category===category).forEach(c=>chosen.delete(c.id));on?chosen.add(id):chosen.delete(id)}function selection(){return {project_name:document.querySelector('#name').value,components:[...chosen],settings:{tier:'deterministic',runtime:'sync',embedding_dimensions:Number(document.querySelector('#dims').value),chunk_size_words:350,chunk_overlap_words:60}}}
async function validate(){const r=await fetch('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selection())});const x=await r.json();document.querySelector('#status').textContent=x.valid?' Compatible':x.issues.map(i=>i.message).join('\n')}
async function download(kind){const r=await fetch('/api/generate/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selection())});if(!r.ok){document.querySelector('#status').textContent=JSON.stringify(await r.json());return}const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download='rag-project.zip';a.click();URL.revokeObjectURL(a.href)}
async function save(){const r=await fetch('/api/configurations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.querySelector('#name').value,selection:selection()})});document.querySelector('#status').textContent=r.ok?' Saved':' Save failed: '+JSON.stringify(await r.json())}init();
</script></body></html>'''


if __name__ == "__main__":
    serve()
