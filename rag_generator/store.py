from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class ConfigurationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS configurations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def save(self, name: str, payload: dict[str, Any], config_id: str | None = None) -> str:
        identifier = config_id or str(uuid.uuid4())
        encoded = json.dumps(payload, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO configurations (id, name, payload) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP""",
                (identifier, name, encoded),
            )
        return identifier

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, created_at, updated_at FROM configurations ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, config_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, payload, created_at, updated_at FROM configurations WHERE id = ?",
                (config_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["selection"] = json.loads(result.pop("payload"))
        return result

    def delete(self, config_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM configurations WHERE id = ?", (config_id,))
        return cursor.rowcount > 0
