from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["implemented", "proposed"]
RuntimeMode = Literal["sync", "async", "either"]


@dataclass(frozen=True)
class Component:
    id: str
    version: str
    category: str
    name: str
    description: str
    status: Status
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    runtime: RuntimeMode = "either"
    embedding_dimensions: tuple[int, ...] = ()
    tradeoffs: str = ""
    env: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Component:
        list_fields = {
            key: tuple(value.get(key, ()))
            for key in ("provides", "requires", "conflicts", "embedding_dimensions", "env")
        }
        return cls(**{key: item for key, item in value.items() if key not in list_fields}, **list_fields)


@dataclass(frozen=True)
class Selection:
    project_name: str
    components: tuple[str, ...]
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Selection:
        allowed = {"project_name", "components", "settings"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown selection fields: {', '.join(sorted(unknown))}")
        return cls(
            project_name=str(value["project_name"]),
            components=tuple(value["components"]),
            settings=dict(value.get("settings", {})),
        )


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
