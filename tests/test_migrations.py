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
    database_url = f"sqlite+aiosqlite:///{database_path}"

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


def test_correspondent_delete_migration_makes_mail_reference_nullable_without_cascade(tmp_path) -> None:
    database_path = tmp_path / "contact-delete.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"

    _run_alembic(database_url, "upgrade", "20260729_0005")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, language_code, approved_at, created_at, updated_at
            )
            VALUES (2, NULL, 'Owner', NULL, NULL, NULL, '2026-07-15 00:00:00', '2026-07-15 00:00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO correspondents (owner_id, name, note, created_at, updated_at)
            VALUES (1, 'Masha', NULL, '2026-07-15 00:00:00', '2026-07-15 00:00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO mail_items (
                owner_id, correspondent_id, direction, sent_at, received_at, note,
                origin_country_code, origin_city, destination_country_code, destination_city,
                created_at, updated_at
            )
            VALUES (
                1, 1, 'outgoing', '2026-07-15', NULL, NULL,
                NULL, NULL, NULL, NULL,
                '2026-07-15 00:00:00', '2026-07-15 00:00:00'
            )
            """
        )
        connection.commit()

    _run_alembic(database_url, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        nullable = connection.execute("PRAGMA table_info(mail_items)").fetchall()[1][3]
        foreign_keys = connection.execute("PRAGMA foreign_key_list(mail_items)").fetchall()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("UPDATE mail_items SET correspondent_id = NULL WHERE id = 1")
        row = connection.execute("SELECT correspondent_id FROM mail_items WHERE id = 1").fetchone()

    assert nullable == 0
    assert any(fk[2] == "correspondents" and fk[6].upper() != "CASCADE" for fk in foreign_keys)
    assert row == (None,)
