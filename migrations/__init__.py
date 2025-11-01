"""Simple migration runner for Logbook."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import List, Set

from sqlalchemy import text

from extensions import db


def _ensure_migration_table() -> None:
    """Create the schema_migrations table if it does not exist."""
    db.session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.session.commit()


def _load_migration_modules() -> List:
    """Load migration modules ordered by filename."""
    versions_dir = Path(__file__).resolve().parent / "versions"
    modules: List = []
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module_name = f"{__name__}.versions.{path.stem}"
        modules.append(import_module(module_name))
    return modules


def run_migrations() -> None:
    """Apply pending migrations."""
    _ensure_migration_table()

    applied_rows = db.session.execute(text("SELECT version FROM schema_migrations"))
    applied: Set[str] = {row[0] for row in applied_rows}

    for module in _load_migration_modules():
        version = getattr(module, "revision", module.__name__)
        if version in applied:
            continue
        upgrade = getattr(module, "upgrade", None)
        if upgrade is None:
            continue
        upgrade()
        db.session.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {"version": version},
        )
        db.session.commit()


__all__ = ["run_migrations"]