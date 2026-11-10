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
<title>RAG Studio — Build your retrieval stack</title><style>
:root{--ink:#17201b;--muted:#637069;--line:#dfe6e1;--paper:#fff;--wash:#f5f7f5;--green:#12633c;--green-2:#e8f5ed;--navy:#12251d;--amber:#9a5b08;--amber-bg:#fff7e8;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--wash)}*{box-sizing:border-box}body{margin:0;line-height:1.5}button,input,select{font:inherit}button{cursor:pointer}.hero{background:radial-gradient(circle at 85% 10%,#2b6849 0,transparent 34%),linear-gradient(135deg,#0d2118,#173c2b);color:#fff;padding:64px 24px 76px}.hero-inner{max-width:1160px;margin:auto}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:750;color:#9fd4b6}.hero h1{font-size:clamp(38px,6vw,64px);line-height:1.02;letter-spacing:-.045em;margin:13px 0 18px;max-width:780px}.hero p{color:#c7d8cf;font-size:18px;max-width:690px;margin:0}.shell{max-width:1160px;margin:-32px auto 120px;padding:0 24px}.setup{display:grid;grid-template-columns:1.5fr .7fr .8fr;gap:16px;background:var(--paper);padding:20px;border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 50px rgba(22,44,32,.1)}.field label{display:block;font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:7px}.field input,.field select{width:100%;height:46px;border:1px solid #cfd8d2;border-radius:10px;padding:0 13px;background:#fff;color:var(--ink);outline:none}.field input:focus,.field select:focus{border-color:var(--green);box-shadow:0 0 0 3px rgba(18,99,60,.1)}.progress-wrap{margin:30px 2px 8px;display:flex;align-items:center;gap:15px}.progress-track{height:8px;background:#e2e8e4;border-radius:20px;overflow:hidden;flex:1}.progress-fill{height:100%;width:0;background:linear-gradient(90deg,#168b51,#42b876);transition:width .25s}.progress-copy{font-size:13px;color:var(--muted);white-space:nowrap}.intro{padding:34px 2px 8px}.intro h2{font-size:30px;letter-spacing:-.03em;margin:0 0 8px}.intro p{margin:0;color:var(--muted);max-width:760px}.workflow{display:flex;gap:7px;align-items:center;margin:22px 0 6px;overflow:auto;padding-bottom:5px}.workflow span{font-size:12px;font-weight:700;color:#40604f;background:#e9efeb;padding:7px 10px;border-radius:999px;white-space:nowrap}.workflow i{color:#98a69e;font-style:normal}.stage{background:var(--paper);border:1px solid var(--line);border-radius:20px;margin:18px 0;padding:26px}.stage-head{display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:start;margin-bottom:20px}.step{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:var(--navy);color:#fff;font-weight:800}.stage h3{font-size:22px;letter-spacing:-.02em;margin:0 0 4px}.stage-desc{color:var(--muted);margin:0;max-width:740px}.requirement{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;padding:6px 9px;border-radius:99px;background:var(--green-2);color:var(--green)}.requirement.optional{background:#eef1f4;color:#5e6971}.options{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:12px}.option{position:relative;display:block;border:1px solid var(--line);border-radius:14px;padding:17px 17px 16px;cursor:pointer;background:#fff;transition:.18s ease;min-height:155px}.option:hover{border-color:#92ad9d;transform:translateY(-1px);box-shadow:0 8px 22px rgba(23,54,37,.07)}.option.selected{border-color:var(--green);box-shadow:0 0 0 2px rgba(18,99,60,.12);background:#fbfefc}.option.locked{background:#f4f5f4;color:#879089;cursor:not-allowed}.option.locked:hover{transform:none;box-shadow:none;border-color:var(--line)}.option input{position:absolute;right:15px;top:15px;width:18px;height:18px;accent-color:var(--green)}.option-title{font-weight:780;padding-right:58px;margin-bottom:6px}.option-desc{font-size:13px;color:#4f5d55;margin-bottom:10px}.tradeoff{font-size:12px;color:#78847d;border-top:1px solid #edf0ee;padding-top:9px}.selected .option-title{color:var(--green)}.info-wrap{position:absolute;right:42px;top:13px;z-index:2}.info{width:22px;height:22px;border:1px solid #aab6ae;border-radius:50%;background:#fff;color:#536058;font-size:12px;font-weight:800;padding:0}.tooltip{display:none;position:absolute;right:0;top:28px;width:280px;background:#14251c;color:#fff;padding:11px 13px;border-radius:9px;font-size:12px;font-weight:500;box-shadow:0 8px 24px rgba(0,0,0,.2);line-height:1.45}.info-wrap:hover .tooltip,.info:focus+.tooltip{display:block}.credentials{border-color:#bed8c8;background:#fbfefc}.credential-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.credential-card{border:1px solid #d6e5dc;background:#fff;border-radius:13px;padding:16px}.credential-label{display:flex;align-items:center;gap:8px;font-weight:780;margin-bottom:7px}.credential-label .info-wrap{position:relative;right:auto;top:auto}.credential-label .tooltip{left:0;right:auto}.credential-card input{width:100%;height:44px;border:1px solid #c9d5cd;border-radius:9px;padding:0 12px}.credential-note{font-size:12px;color:var(--muted);margin:8px 0 0}.credential-actions{display:flex;align-items:center;gap:9px;margin-top:15px}.local-badge{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:var(--green);background:var(--green-2);padding:5px 8px;border-radius:99px}.coming{margin-top:36px;padding:25px;border:1px dashed #d8c295;background:var(--amber-bg);border-radius:18px}.coming h2{font-size:21px;margin:0 0 5px}.coming>p{margin:0 0 18px;color:#775b32}.coming-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.soon{position:relative;background:rgba(255,255,255,.7);border:1px solid #eadaba;border-radius:12px;padding:14px}.soon b{display:block;margin-bottom:4px}.soon span{font-size:12px;color:#806d50}.soon-tag{display:inline-block!important;font-size:10px!important;text-transform:uppercase;letter-spacing:.07em;font-weight:800;color:var(--amber)!important;margin-top:9px}.actionbar{position:fixed;z-index:10;left:0;right:0;bottom:0;background:rgba(255,255,255,.94);backdrop-filter:blur(16px);border-top:1px solid var(--line);padding:13px 24px}.actions{max-width:1160px;margin:auto;display:flex;align-items:center;gap:9px}.button{border:1px solid #ccd6d0;border-radius:10px;padding:10px 15px;background:#fff;color:#26332b;font-weight:700}.button:hover{background:#f4f7f5}.button.primary{background:var(--green);border-color:var(--green);color:#fff}.button.primary:hover{background:#0d5432}.status{margin-left:auto;font-size:13px;color:var(--muted);white-space:pre-wrap;max-width:360px}.status.ok{color:var(--green);font-weight:700}.status.error{color:#a2322a}.mobile-summary{display:none}@media(max-width:760px){.hero{padding-top:42px}.shell{padding:0 14px}.setup{grid-template-columns:1fr}.stage{padding:20px}.stage-head{grid-template-columns:42px 1fr}.requirement{grid-column:2;justify-self:start}.actions{overflow:auto}.status{display:none}.mobile-summary{display:block;font-size:12px;margin-left:auto}.button{white-space:nowrap}}
</style></head><body>
<header class="hero"><div class="hero-inner"><div class="eyebrow">RAG Studio</div><h1>Build the retrieval stack your product actually needs.</h1><p>Choose one clear option at each required stage. We validate compatibility, explain the trade-offs, and generate a runnable codebase.</p></div></header>
<main class="shell"><section class="setup" aria-label="Project settings"><div class="field"><label for="name">Project name</label><input id="name" value="my-rag-service" autocomplete="off"></div><div class="field"><label for="dims">Vector dimensions</label><select id="dims"><option>1536</option><option>768</option><option>384</option></select></div><div class="field"><label>Architecture</label><select disabled><option>Deterministic RAG</option></select></div></section>
<div class="progress-wrap"><div class="progress-track"><div id="progress" class="progress-fill"></div></div><div id="progress-copy" class="progress-copy">0 of 5 required stages complete</div></div>
<section class="intro"><h2>Your RAG pipeline</h2><p>A RAG system turns documents into searchable evidence, retrieves the best evidence for each question, and measures whether retrieval is working.</p><div class="workflow"><span>Documents</span><i>→</i><span>Chunks</span><i>→</i><span>Embeddings</span><i>→</i><span>Index</span><i>→</i><span>Retrieval</span><i>→</i><span>Evaluation</span></div></section>
<div id="catalog"></div><section id="credentials" class="stage credentials" hidden><div class="stage-head"><div class="step">09</div><div><h3>Provider credentials</h3><p class="stage-desc">AI-backed options need provider keys at runtime. Enter them only after your architecture is selected.</p></div><span class="requirement">Required for AI</span></div><div id="credential-grid" class="credential-grid"></div><div class="credential-actions"><button class="button" type="button" onclick="downloadEnv()">Download private .env</button><span class="local-badge">Browser-local only</span></div></section><section id="coming" class="coming"><h2>Coming soon</h2><p>These options are intentionally unavailable because their code adapters are not production-ready yet—not because your browser is broken.</p><div id="coming-grid" class="coming-grid"></div></section></main>
<footer class="actionbar"><div class="actions"><button class="button" onclick="validateConfig()">Check compatibility</button><button class="button" onclick="saveConfig()">Save</button><button class="button" onclick="downloadProject('module')">Download modules</button><button class="button primary" onclick="downloadProject('repository')">Generate repository</button><span id="status" class="status"></span><span id="mobile-summary" class="mobile-summary"></span></div></footer>
<script>
const sections={parser:{step:'01',title:'Document parsing',description:'Extract clean text and useful structure from the files your users upload.',required:true},chunker:{step:'02',title:'Chunking strategy',description:'Split documents into retrieval units. Chunk boundaries strongly affect answer quality and citation clarity.',required:true},embedding:{step:'03',title:'Embedding model',description:'Turn each chunk and question into vectors whose distance represents semantic similarity.',required:true},vector_store:{step:'04',title:'Vector storage',description:'Store vectors beside text and metadata so retrieval can be filtered, authorized, and fast.',required:true},retrieval:{step:'05',title:'Retrieval strategy',description:'Choose how the most relevant evidence is found before it reaches the answer model.',required:true},fusion:{step:'06',title:'Rank fusion',description:'Combine independent result lists without comparing incompatible raw scores.',required:false},queue:{step:'07',title:'Background ingestion',description:'Move document processing into a restartable worker for larger files and production workloads.',required:false},metric:{step:'08',title:'Evaluation metrics',description:'Select multiple signals to measure coverage, ranking quality, and regression over time.',required:false}};
const required=['parser','chunker','embedding','vector_store','retrieval'];const single=new Set(['chunker','embedding','vector_store','retrieval']);let components=[];const chosen=new Set();const credentialValues=new Map();
function safe(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function unlockMessage(c){if(c.id==='fusion.rrf'&&!chosen.has('retrieval.hybrid'))return 'To enable this option, choose Hybrid Retrieval in the previous section.';return ''}
function learnMessage(c){const keyNote=c.env.some(name=>name.endsWith('API_KEY'))?` This option requires ${c.env.filter(name=>name.endsWith('API_KEY')).join(', ')}; you will enter it privately in the final Credentials step.`:'';return `${c.description} When to choose it: ${c.tradeoffs}${keyNote} ${unlockMessage(c)}`.trim()}
function infoControl(message,label='Learn more'){return `<span class="info-wrap"><button class="info" type="button" aria-label="${safe(label)}">i</button><span class="tooltip" role="tooltip">${safe(message)}</span></span>`}
function option(c){const type=single.has(c.category)?'radio':'checkbox';return `<label class="option" data-id="${safe(c.id)}">${infoControl(learnMessage(c),`Learn about ${c.name}`)}<input aria-label="${safe(c.name)}" type="${type}" name="${single.has(c.category)?safe(c.category):safe(c.id)}" onchange="choose('${safe(c.id)}','${safe(c.category)}',this.checked)"><div class="option-title">${safe(c.name)}</div><div class="option-desc">${safe(c.description)}</div><div class="tradeoff">${safe(c.tradeoffs)}</div></label>`}
function render(){const ready=components.filter(c=>c.status==='implemented');document.querySelector('#catalog').innerHTML=Object.entries(sections).map(([category,meta])=>{const items=ready.filter(c=>c.category===category);if(!items.length)return '';return `<section class="stage"><div class="stage-head"><div class="step">${meta.step}</div><div><h3>${meta.title}</h3><p class="stage-desc">${meta.description}</p></div><span class="requirement ${meta.required?'':'optional'}">${meta.required?'Required':'Optional'}</span></div><div class="options">${items.map(option).join('')}</div></section>`}).join('');const proposed=components.filter(c=>c.status==='proposed');document.querySelector('#coming').hidden=!proposed.length;document.querySelector('#coming-grid').innerHTML=proposed.map(c=>`<article class="soon"><b>${safe(c.name)}</b><span>${safe(c.description)}</span><span class="soon-tag">Adapter in development</span></article>`).join('');updateUI()}
function choose(id,category,on){if(single.has(category))components.filter(c=>c.category===category).forEach(c=>chosen.delete(c.id));if(category==='retrieval'&&id!=='retrieval.hybrid')chosen.delete('fusion.rrf');if(on)chosen.add(id);else chosen.delete(id);updateUI();renderCredentials();clearStatus()}
function updateUI(){document.querySelectorAll('.option').forEach(card=>{const id=card.dataset.id;const locked=id==='fusion.rrf'&&!chosen.has('retrieval.hybrid');if(locked)chosen.delete(id);const on=chosen.has(id);card.classList.toggle('selected',on);card.classList.toggle('locked',locked);card.querySelector('input').disabled=locked;card.querySelector('input').checked=on});const done=required.filter(category=>components.some(c=>c.category===category&&chosen.has(c.id))).length;document.querySelector('#progress').style.width=`${done/required.length*100}%`;document.querySelector('#progress-copy').textContent=`${done} of ${required.length} required stages complete`;document.querySelector('#mobile-summary').textContent=`${done}/${required.length} complete`}
function requiredApiKeys(){return [...new Set(components.filter(c=>chosen.has(c.id)).flatMap(c=>c.env).filter(name=>name.endsWith('API_KEY')))]}
function renderCredentials(){const keys=requiredApiKeys();const section=document.querySelector('#credentials');section.hidden=!keys.length;document.querySelector('#credential-grid').innerHTML=keys.map(name=>`<div class="credential-card"><div class="credential-label"><span>${safe(name)}</span>${infoControl('This secret stays in this browser tab. It is never sent to the generator or saved with your configuration.',`Learn about ${name}`)}</div><input type="password" autocomplete="off" aria-label="${safe(name)}" placeholder="Enter ${safe(name)}" value="${safe(credentialValues.get(name)||'')}" oninput="credentialValues.set('${safe(name)}',this.value)"><p class="credential-note">Required when the generated application calls this provider.</p></div>`).join('')}
function selection(){return {project_name:document.querySelector('#name').value,components:[...chosen],settings:{tier:'deterministic',runtime:chosen.has('queue.arq')?'async':'sync',embedding_dimensions:Number(document.querySelector('#dims').value),chunk_size_words:350,chunk_overlap_words:60}}}
function setStatus(message,type=''){const el=document.querySelector('#status');el.textContent=message;el.className=`status ${type}`}
function clearStatus(){setStatus('')}
async function validateConfig(){setStatus('Checking…');const r=await fetch('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selection())});const x=await r.json();setStatus(x.valid?'✓ Your stack is compatible':x.issues.map(i=>i.message).join('\n'),x.valid?'ok':'error')}
function missingCredentials(){return requiredApiKeys().filter(name=>!(credentialValues.get(name)||'').trim())}
function downloadEnv(){const missing=missingCredentials();if(missing.length){setStatus(`Enter ${missing.join(', ')} first`,'error');return}const body=requiredApiKeys().map(name=>`${name}=${credentialValues.get(name)}`).join('\n')+'\n';const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{type:'text/plain'}));a.download='.env';a.click();URL.revokeObjectURL(a.href);setStatus('✓ Private .env downloaded locally','ok')}
async function downloadProject(kind){const missing=missingCredentials();if(missing.length){document.querySelector('#credentials').scrollIntoView({behavior:'smooth'});setStatus(`Enter ${missing.join(', ')} in the final Credentials step`,'error');return}setStatus('Building your files…');const r=await fetch('/api/generate/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selection())});if(!r.ok){const x=await r.json();setStatus((x.issues||[]).map(i=>i.message).join('\n')||'Generation failed','error');return}const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=kind==='repository'?'rag-project.zip':'rag-modules.zip';a.click();URL.revokeObjectURL(a.href);setStatus('✓ Download ready','ok')}
async function saveConfig(){setStatus('Saving…');const r=await fetch('/api/configurations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.querySelector('#name').value,selection:selection()})});setStatus(r.ok?'✓ Configuration saved':'Could not save configuration',r.ok?'ok':'error')}
async function init(){components=(await(await fetch('/api/catalog')).json()).components;['parser.text','chunker.fixed','embedding.hash','store.pgvector','retrieval.vector','metric.hit_at_k','metric.recall_at_k','metric.mrr'].forEach(id=>chosen.add(id));render();renderCredentials()}init();
</script></body></html>'''


if __name__ == "__main__":
    serve()
