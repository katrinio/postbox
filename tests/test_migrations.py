"""Alembic migration checks for SQLite production compatibility."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["POSTBOX_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=Path(__file__).parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_mail_geography_migration_preserves_existing_sqlite_rows(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"

    _run_alembic(database_url, "upgrade", "20260719_0003")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, language_code, created_at, updated_at
            )
            VALUES (1, NULL, 'Owner', NULL, NULL, '2026-07-15 00:00:00', '2026-07-15 00:00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO correspondents (owner_id, name, created_at, updated_at)
            VALUES (1, 'Masha', '2026-07-15 00:00:00', '2026-07-15 00:00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO mail_items (
                owner_id, correspondent_id, direction, sent_at, received_at, note, created_at, updated_at
            )
            VALUES (
                1, 1, 'outgoing', '2026-07-15', NULL, NULL, '2026-07-15 00:00:00', '2026-07-15 00:00:00'
            )
            """
        )
        connection.commit()

    _run_alembic(database_url, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT origin_country_code, origin_city, destination_country_code, destination_city
            FROM mail_items
            WHERE id = 1
            """
        ).fetchone()
        columns = [row[1] for row in connection.execute("PRAGMA table_info(mail_items)").fetchall()]

    assert row == (None, None, None, None)
    assert "origin_country_code" in columns
    assert "origin_city" in columns
    assert "destination_country_code" in columns
    assert "destination_city" in columns

    _run_alembic(database_url, "downgrade", "20260719_0003")

    with sqlite3.connect(database_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(mail_items)").fetchall()]

    assert "origin_country_code" not in columns
    assert "origin_city" not in columns
    assert "destination_country_code" not in columns
    assert "destination_city" not in columns
