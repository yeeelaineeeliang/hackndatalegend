from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DECISION_STATUSES = [
    "confirmed_accurate",
    "needs_review",
    "incorrect_claim",
    "missing_evidence",
    "resolved",
]
DECISION_COLUMNS = [
    "decision_id",
    "facility_id",
    "facility_name",
    "review_status",
    "reviewer",
    "note",
    "decided_at",
]
SQLITE_PATH = Path(
    os.environ.get(
        "REVIEW_DB_PATH",
        Path(__file__).resolve().parent / "data" / "review_decisions.sqlite",
    )
)
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS review_decisions (
    decision_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    facility_name TEXT,
    review_status TEXT NOT NULL,
    reviewer TEXT,
    note TEXT,
    decided_at TEXT NOT NULL
)
"""


class ReviewStore:
    """Durable, append-only store for reviewer decisions.

    Decisions are an audit trail: every submission appends a row, and the
    latest row per facility defines its current review status. Uses Lakebase
    Postgres when the app runs on Databricks Apps with a database resource
    attached (PGHOST is injected), otherwise a local SQLite file.
    """

    def __init__(self) -> None:
        self.backend = "sqlite"
        self.backend_detail = str(SQLITE_PATH)
        self._pg_password: str | None = None
        if os.environ.get("PGHOST"):
            try:
                self._ensure_schema_postgres()
                self.backend = "lakebase"
                self.backend_detail = (
                    f"{os.environ['PGHOST']}/"
                    f"{os.environ.get('PGDATABASE', 'databricks_postgres')}"
                )
            except Exception as error:  # noqa: BLE001 - fall back, keep reason
                self.backend = "sqlite"
                self.backend_detail = f"{SQLITE_PATH} (Lakebase unavailable: {error})"
        if self.backend == "sqlite":
            self._ensure_schema_sqlite()

    # -- connections -----------------------------------------------------

    def _pg_connect(self):
        import psycopg

        password = os.environ.get("PGPASSWORD") or self._pg_password
        if not password:
            from databricks.sdk import WorkspaceClient

            password = WorkspaceClient().config.oauth_token().access_token
            self._pg_password = password
        try:
            return psycopg.connect(
                host=os.environ["PGHOST"],
                port=int(os.environ.get("PGPORT", "5432")),
                dbname=os.environ.get("PGDATABASE", "databricks_postgres"),
                user=os.environ.get("PGUSER"),
                password=password,
                sslmode=os.environ.get("PGSSLMODE", "require"),
            )
        except psycopg.OperationalError:
            # OAuth tokens expire roughly hourly; refresh once and retry.
            self._pg_password = None
            if os.environ.get("PGPASSWORD"):
                raise
            from databricks.sdk import WorkspaceClient

            self._pg_password = WorkspaceClient().config.oauth_token().access_token
            return psycopg.connect(
                host=os.environ["PGHOST"],
                port=int(os.environ.get("PGPORT", "5432")),
                dbname=os.environ.get("PGDATABASE", "databricks_postgres"),
                user=os.environ.get("PGUSER"),
                password=self._pg_password,
                sslmode=os.environ.get("PGSSLMODE", "require"),
            )

    def _sqlite_connect(self) -> sqlite3.Connection:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(SQLITE_PATH)

    def _ensure_schema_postgres(self) -> None:
        with self._pg_connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
            connection.commit()

    def _ensure_schema_sqlite(self) -> None:
        with self._sqlite_connect() as connection:
            connection.execute(CREATE_TABLE_SQL)
            connection.commit()

    # -- operations ------------------------------------------------------

    def append_decision(
        self,
        *,
        facility_id: str,
        facility_name: str,
        review_status: str,
        reviewer: str,
        note: str,
    ) -> str:
        if review_status not in DECISION_STATUSES:
            raise ValueError(f"Unknown review status: {review_status}")
        decision_id = str(uuid.uuid4())
        row = (
            decision_id,
            facility_id,
            facility_name,
            review_status,
            reviewer.strip() or "anonymous reviewer",
            note.strip(),
            datetime.now(timezone.utc).isoformat(),
        )
        insert_sql = (
            "INSERT INTO review_decisions "
            "(decision_id, facility_id, facility_name, review_status, "
            "reviewer, note, decided_at) VALUES ({placeholders})"
        )
        if self.backend == "lakebase":
            with self._pg_connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        insert_sql.format(placeholders="%s, %s, %s, %s, %s, %s, %s"),
                        row,
                    )
                connection.commit()
        else:
            with self._sqlite_connect() as connection:
                connection.execute(
                    insert_sql.format(placeholders="?, ?, ?, ?, ?, ?, ?"), row
                )
                connection.commit()
        return decision_id

    def load_decisions(self) -> pd.DataFrame:
        query = (
            "SELECT decision_id, facility_id, facility_name, review_status, "
            "reviewer, note, decided_at FROM review_decisions "
            "ORDER BY decided_at DESC"
        )
        if self.backend == "lakebase":
            with self._pg_connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
        else:
            with self._sqlite_connect() as connection:
                rows = connection.execute(query).fetchall()
        return pd.DataFrame(rows, columns=DECISION_COLUMNS)

    def latest_decisions(self) -> pd.DataFrame:
        decisions = self.load_decisions()
        if decisions.empty:
            return decisions
        return decisions.drop_duplicates("facility_id", keep="first")
