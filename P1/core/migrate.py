"""스키마 버전 관리. 새 버전은 MIGRATIONS에 번호를 올려 추가한다."""
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS records (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        source TEXT NOT NULL,
        key TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        UNIQUE(source, key)
    );
    CREATE INDEX IF NOT EXISTS idx_records_kind_seq ON records(kind, seq);
    CREATE TABLE IF NOT EXISTS raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        body TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS source_status (
        source TEXT PRIMARY KEY,
        last_success_at TEXT,
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        last_run_at TEXT
    );
    """,
}


def migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    for v in sorted(MIGRATIONS):
        if v in done:
            continue
        conn.executescript(MIGRATIONS[v])
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (v, datetime.now(KST).isoformat(timespec="seconds")),
        )
    conn.commit()
