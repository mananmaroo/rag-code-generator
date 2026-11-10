"""FastAPI entrypoint used by Vercel's Python runtime."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from rag_generator.archive import module_zip, repository_zip
from rag_generator.catalog import load_catalog
from rag_generator.compatibility import validate_selection
from rag_generator.models import Selection
from rag_generator.store import ConfigurationStore
from rag_generator.web import UI, component_payload

app = FastAPI(title="RAG Studio", docs_url=None, redoc_url=None)
catalog = load_catalog()
store = ConfigurationStore(Path("/tmp/rag-code-generator.db"))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'"
    )
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return UI


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "catalog_components": len(catalog)}


@app.get("/api/catalog")
def get_catalog() -> dict[str, object]:
    return {"components": [component_payload(item) for item in catalog.values()]}


@app.post("/api/validate")
async def validate(request: Request) -> dict[str, object]:
    selection = Selection.from_dict(await request.json())
    issues = validate_selection(selection, catalog)
    return {"valid": not issues, "issues": [issue.__dict__ for issue in issues]}


@app.get("/api/configurations")
def list_configurations() -> dict[str, object]:
    return {"configurations": store.list()}


@app.get("/api/configurations/{config_id}")
def get_configuration(config_id: str):
    value = store.get(config_id)
    if value is None:
        raise HTTPException(status_code=404, detail="not_found")
    return value


@app.post("/api/configurations", status_code=201)
async def save_configuration(request: Request):
    body = await request.json()
    selection = Selection.from_dict(body["selection"])
    issues = validate_selection(selection, catalog, require_implemented=False)
    if issues:
        return JSONResponse(
            {"error": "invalid_selection", "issues": [issue.__dict__ for issue in issues]},
            status_code=422,
        )
    identifier = store.save(
        str(body.get("name") or selection.project_name), body["selection"], body.get("id")
    )
    return {"id": identifier}


@app.delete("/api/configurations/{config_id}")
def delete_configuration(config_id: str):
    if not store.delete(config_id):
        raise HTTPException(status_code=404, detail="not_found")
    return {"deleted": True}


async def _generate(request: Request, *, modules_only: bool) -> Response:
    selection = Selection.from_dict(await request.json())
    issues = validate_selection(selection, catalog)
    if issues:
        return JSONResponse(
            {"error": "invalid_selection", "issues": [issue.__dict__ for issue in issues]},
            status_code=422,
        )
    components = [catalog[item] for item in selection.components]
    content = module_zip(selection, components) if modules_only else repository_zip(selection, components)
    filename = "rag-modules.zip" if modules_only else "rag-project.zip"
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/generate/repository")
async def generate_repository_endpoint(request: Request) -> Response:
    return await _generate(request, modules_only=False)


@app.post("/api/generate/module")
async def generate_module_endpoint(request: Request) -> Response:
    return await _generate(request, modules_only=True)

