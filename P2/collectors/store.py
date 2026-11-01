"""Supabase(PostgREST) 저장소. 테이블: raw, records, source_status (마이그레이션 create_core_tables_v1).

- service_role 키는 환경변수 SUPABASE_SERVICE_ROLE_KEY에서만 읽고 출력하지 않는다.
- records는 (source, key) 기준으로 갱신(upsert)하므로 같은 데이터를 여러 번 넣어도 중복이 생기지 않는다.
"""
import os
from datetime import datetime, timedelta, timezone

from .net import request_json

KST = timezone(timedelta(hours=9))
CHUNK = 500  # 한 번에 보내는 행 수


def now_iso():
    return datetime.now(KST).isoformat(timespec="seconds")


class SupabaseStore:
    def __init__(self, url=None, key=None):
        base = url or os.environ["SUPABASE_URL"]
        self.base = base.rstrip("/") + "/rest/v1"
        self.key = key or os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    def _headers(self, prefer=None):
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        if prefer:
            h["Prefer"] = prefer
        return h

    def save_raw(self, source, payload, http_status=200):
        """원본 응답을 raw에 한 행으로 저장하고 id를 돌려준다. 재시도하면 중복 행이 생기므로 재시도하지 않는다."""
        rows = request_json(
            "POST", f"{self.base}/raw",
            headers=self._headers("return=representation"),
            body={"source": source, "http_status": http_status, "payload": payload},
            retries=0,
        )
        return rows[0]["id"]

    def upsert_records(self, kind, source, items, raw_id=None):
        """items: [{key, observed_at, payload}]. 반환: 보낸 행 수."""
        total = 0
        for i in range(0, len(items), CHUNK):
            rows = [{
                "source": source,
                "kind": kind,
                "key": it["key"],
                "observed_on": it["observed_at"],
                "data": it["payload"],
                "raw_id": raw_id,
            } for it in items[i:i + CHUNK]]
            request_json(
                "POST", f"{self.base}/records",
                params={"on_conflict": "source,key"},
                headers=self._headers("resolution=merge-duplicates,return=minimal"),
                body=rows,
            )
            total += len(rows)
        return total

    def get_status(self, source):
        rows = request_json(
            "GET", f"{self.base}/source_status",
            params={"source": f"eq.{source}", "select": "*"},
            headers=self._headers(),
        )
        return rows[0] if rows else None

    def set_ok(self, source):
        t = now_iso()
        self._write_status({
            "source": source,
            "last_success_at": t,
            "consecutive_failures": 0,
            "last_error": None,
            "updated_at": t,
        })

    def set_error(self, source, message):
        cur = self.get_status(source) or {}
        self._write_status({
            "source": source,
            "consecutive_failures": int(cur.get("consecutive_failures") or 0) + 1,
            "last_error": str(message)[:300],
            "updated_at": now_iso(),
        })

    def _write_status(self, row):
        request_json(
            "POST", f"{self.base}/source_status",
            params={"on_conflict": "source"},
            headers=self._headers("resolution=merge-duplicates,return=minimal"),
            body=row,
        )
