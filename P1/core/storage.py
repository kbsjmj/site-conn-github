"""저장소: records(범용 레코드, seq 증분), raw(원본 응답), source_status(소스별 상태). SQLite WAL."""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .migrate import migrate

KST = timezone(timedelta(hours=9))


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        migrate(self.conn)

    def close(self):
        self.conn.close()

    def save_raw(self, source, body_text):
        self.conn.execute(
            "INSERT INTO raw(source, fetched_at, body) VALUES (?, ?, ?)",
            (source, now_iso(), body_text),
        )
        self.conn.commit()

    def upsert_records(self, kind, source, items):
        """items: [{key, observed_at, payload}]. 반환: (신규 수, 갱신 수). seq는 처음 저장된 값을 유지한다."""
        inserted = updated = 0
        fetched = now_iso()
        for it in items:
            exists = self.conn.execute(
                "SELECT 1 FROM records WHERE source = ? AND key = ?", (source, it["key"])
            ).fetchone()
            self.conn.execute(
                """
                INSERT INTO records(kind, source, key, observed_at, fetched_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, key) DO UPDATE SET
                    observed_at = excluded.observed_at,
                    fetched_at = excluded.fetched_at,
                    payload = excluded.payload
                """,
                (kind, source, it["key"], it["observed_at"], fetched,
                 json.dumps(it["payload"], ensure_ascii=False, sort_keys=True)),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
        self.conn.commit()
        return inserted, updated

    def set_status_ok(self, source):
        t = now_iso()
        self.conn.execute(
            """
            INSERT INTO source_status(source, last_success_at, consecutive_failures, last_error, last_run_at)
            VALUES (?, ?, 0, NULL, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_success_at = excluded.last_success_at,
                consecutive_failures = 0,
                last_error = NULL,
                last_run_at = excluded.last_run_at
            """,
            (source, t, t),
        )
        self.conn.commit()

    def set_status_error(self, source, message):
        t = now_iso()
        self.conn.execute(
            """
            INSERT INTO source_status(source, consecutive_failures, last_error, last_run_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                consecutive_failures = consecutive_failures + 1,
                last_error = excluded.last_error,
                last_run_at = excluded.last_run_at
            """,
            (source, str(message)[:300], t),
        )
        self.conn.commit()

    def statuses(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM source_status ORDER BY source")]

    def latest(self, kind, source=None, limit=10):
        q = "SELECT * FROM records WHERE kind = ?"
        args = [kind]
        if source:
            q += " AND source = ?"
            args.append(source)
        q += " ORDER BY observed_at DESC, seq DESC LIMIT ?"
        args.append(limit)
        return [self._row(r) for r in self.conn.execute(q, args)]

    def recent(self, kind, limit=50):
        """seq 내림차순 최신 레코드."""
        rows = self.conn.execute(
            "SELECT * FROM records WHERE kind = ? ORDER BY seq DESC LIMIT ?", (kind, limit))
        return [self._row(r) for r in rows]

    def after(self, kind, after_seq=0, limit=100):
        rows = self.conn.execute(
            "SELECT * FROM records WHERE kind = ? AND seq > ? ORDER BY seq LIMIT ?",
            (kind, after_seq, limit),
        )
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        return d
