"""Transactional local run history. No pickle deserialization or shared global state."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def default_database() -> Path:
    """Use an explicit override or an ignored, local data directory."""
    return Path(os.environ.get("DEMOGRAPHICS_DB", "data/simulations.sqlite3"))


class RunStore:
    """Persist complete experiments in atomic SQLite transactions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_database()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
                    engine TEXT NOT NULL, duration REAL NOT NULL,
                    parameters TEXT NOT NULL, summary TEXT NOT NULL, result TEXT NOT NULL
                )
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Create a short-lived connection usable across independent UI sessions."""
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, name: str, result: dict[str, Any]) -> str:
        """Store result, metadata, and parameters together or not at all."""
        identifier = uuid4().hex
        created = datetime.now(UTC).isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    name.strip()[:120] or "Untitled simulation",
                    created,
                    result["engine"],
                    result["duration_seconds"],
                    json.dumps(result["parameters"], allow_nan=False),
                    json.dumps(result["summary"], allow_nan=False),
                    json.dumps(result, allow_nan=False, separators=(",", ":")),
                ),
            )
        return identifier

    def list_runs(self) -> list[dict[str, Any]]:
        """Read metadata only, leaving potentially large population snapshots on disk."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, created_at, engine, duration, parameters, summary "
                "FROM runs ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        return [
            dict(row)
            | {"parameters": json.loads(row["parameters"]), "summary": json.loads(row["summary"])}
            for row in rows
        ]

    def load(self, identifier: str) -> dict[str, Any]:
        """Load a run by ID without accepting paths or executable objects."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result FROM runs WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Simulation not found: {identifier}")
        result: dict[str, Any] = json.loads(row["result"])
        return result
