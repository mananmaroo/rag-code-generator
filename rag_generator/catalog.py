import json
from importlib.resources import files

from rag_generator.models import Component


def load_catalog() -> dict[str, Component]:
    path = files("rag_generator").joinpath("catalog/components.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    components = [Component.from_dict(item) for item in payload["components"]]
    by_id = {component.id: component for component in components}
    if len(by_id) != len(components):
        raise ValueError("catalogue contains duplicate component IDs")
    return by_id
