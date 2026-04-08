from __future__ import annotations

import sqlite3
from pathlib import Path

from automation.utils import compact_json


class IdentityStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._ensure_parent_dir()
        self._init_db()

    def _ensure_parent_dir(self) -> None:
        parent = Path(self.path).expanduser().resolve().parent
        parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_mappings (
                    external_company_key TEXT PRIMARY KEY,
                    normalized_company_name TEXT,
                    normalized_domain TEXT,
                    lightfield_account_id TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS contact_mappings (
                    identity_key TEXT PRIMARY KEY,
                    external_company_key TEXT,
                    full_name TEXT,
                    email TEXT,
                    linkedin_url TEXT,
                    lightfield_contact_id TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS processed_events (
                    provider TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, event_key)
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_mode TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS dead_letters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    reference_key TEXT NOT NULL,
                    payload_json TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def get_account_by_external_key(self, external_company_key: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM account_mappings
                WHERE external_company_key = ?
                """,
                (external_company_key,),
            )
            return cursor.fetchone()

    def get_account_by_domain(self, normalized_domain: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM account_mappings
                WHERE normalized_domain = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (normalized_domain,),
            )
            return cursor.fetchone()

    def upsert_account_mapping(
        self,
        *,
        external_company_key: str,
        normalized_company_name: str | None,
        normalized_domain: str | None,
        lightfield_account_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO account_mappings (
                    external_company_key,
                    normalized_company_name,
                    normalized_domain,
                    lightfield_account_id
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(external_company_key)
                DO UPDATE SET
                    normalized_company_name = excluded.normalized_company_name,
                    normalized_domain = excluded.normalized_domain,
                    lightfield_account_id = excluded.lightfield_account_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    external_company_key,
                    normalized_company_name,
                    normalized_domain,
                    lightfield_account_id,
                ),
            )

    def get_contact_by_identity(
        self,
        *,
        email: str | None = None,
        linkedin_url: str | None = None,
        full_name: str | None = None,
        external_company_key: str | None = None,
    ) -> sqlite3.Row | None:
        clauses: list[str] = []
        values: list[str] = []
        if email:
            clauses.append("email = ?")
            values.append(email)
        if linkedin_url:
            clauses.append("linkedin_url = ?")
            values.append(linkedin_url)
        if full_name and external_company_key:
            clauses.append("(full_name = ? AND external_company_key = ?)")
            values.extend([full_name, external_company_key])

        if not clauses:
            return None

        query = f"""
            SELECT * FROM contact_mappings
            WHERE {' OR '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT 1
        """
        with self._connect() as connection:
            cursor = connection.execute(query, values)
            return cursor.fetchone()

    def upsert_contact_mapping(
        self,
        *,
        identity_key: str,
        external_company_key: str,
        full_name: str | None,
        email: str | None,
        linkedin_url: str | None,
        lightfield_contact_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO contact_mappings (
                    identity_key,
                    external_company_key,
                    full_name,
                    email,
                    linkedin_url,
                    lightfield_contact_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(identity_key)
                DO UPDATE SET
                    external_company_key = excluded.external_company_key,
                    full_name = excluded.full_name,
                    email = excluded.email,
                    linkedin_url = excluded.linkedin_url,
                    lightfield_contact_id = excluded.lightfield_contact_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    identity_key,
                    external_company_key,
                    full_name,
                    email,
                    linkedin_url,
                    lightfield_contact_id,
                ),
            )

    def has_processed_event(self, provider: str, event_key: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT 1 FROM processed_events
                WHERE provider = ? AND event_key = ?
                """,
                (provider, event_key),
            )
            return cursor.fetchone() is not None

    def mark_event_processed(self, provider: str, event_key: str, payload: object) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO processed_events (
                    provider,
                    event_key,
                    payload_json
                ) VALUES (?, ?, ?)
                """,
                (provider, event_key, compact_json(payload)),
            )

    def record_sync_run(self, run_mode: str, target_key: str, status: str, message: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_runs (run_mode, target_key, status, message)
                VALUES (?, ?, ?, ?)
                """,
                (run_mode, target_key, status, message),
            )

    def record_dead_letter(
        self,
        *,
        source: str,
        reference_key: str,
        payload: object,
        error_message: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dead_letters (
                    source,
                    reference_key,
                    payload_json,
                    error_message
                ) VALUES (?, ?, ?, ?)
                """,
                (source, reference_key, compact_json(payload), error_message),
            )
