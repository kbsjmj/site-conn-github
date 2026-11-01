"""P2 수집기 단위 테스트. 네트워크와 Supabase 호출은 모두 가짜로 바꾼다 (합성 데이터)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from collectors import dart, fred, run, store as store_mod


def dart_page(page, total_pages, total_count, n):
    return {
        "status": "000",
        "message": "정상",
        "page_no": page,
        "total_page": total_pages,
        "total_count": total_count,
        "list": [{"rcept_no": f"{page:02d}{i:06d}", "rcept_dt": "20261030",
                  "corp_name": "합성", "report_nm": "합성 공시"} for i in range(n)],
    }


class DartTests(unittest.TestCase):
    ENV = {"DART_API_KEY": "TEST"}

    def test_fetch_gets_every_page(self):
        pages = [dart_page(1, 3, 250, 100), dart_page(2, 3, 250, 100), dart_page(3, 3, 250, 50)]
        with mock.patch.object(dart, "get_json", side_effect=pages) as g:
            raw = dart.fetch({"lookback_days": 3}, self.ENV)
        self.assertEqual(len(raw["list"]), 250)
        self.assertEqual(g.call_count, 3)

    def test_count_mismatch_is_an_error(self):
        pages = [dart_page(1, 2, 250, 100), dart_page(2, 2, 250, 100)]  # 200건 (250 기대)
        with mock.patch.object(dart, "get_json", side_effect=pages):
            with self.assertRaisesRegex(ValueError, "건수 불일치"):
                dart.fetch({"lookback_days": 3}, self.ENV)

    def test_too_many_pages_is_an_error(self):
        first = dart_page(1, dart.MAX_PAGES + 1, 9999, 100)
        with mock.patch.object(dart, "get_json", return_value=first):
            with self.assertRaisesRegex(ValueError, "안전 상한"):
                dart.fetch({"lookback_days": 3}, self.ENV)

    def test_no_data_status_normalizes_to_empty(self):
        self.assertEqual(dart.normalize({"status": "013"}, {}), [])

    def test_normalize_builds_keyed_items(self):
        items = dart.normalize(dart_page(1, 1, 1, 1), {})
        self.assertEqual(items[0]["key"], "01000000")
        self.assertEqual(items[0]["observed_at"], "2026-10-30")


class FredTests(unittest.TestCase):
    def test_missing_values_are_skipped(self):
        raw = {"SP500": {"observations": [
            {"date": "2026-10-30", "value": "7580.07"},
            {"date": "2026-10-29", "value": "."},
        ]}}
        items = fred.normalize(raw, {})
        self.assertEqual([i["key"] for i in items], ["SP500:2026-10-30"])
        self.assertEqual(items[0]["payload"]["value"], 7580.07)


class RunTests(unittest.TestCase):
    def test_dedupe_keeps_one_row_per_key(self):
        items = [{"key": "a", "payload": 1}, {"key": "a", "payload": 2}, {"key": "b", "payload": 3}]
        self.assertEqual(len(run.dedupe(items)), 2)

    def test_one_failing_source_does_not_stop_the_others(self):
        cfg = {"sources": [
            {"id": "fred", "status": "active", "keys": ["FRED_API_KEY"], "keep_raw": False, "series": []},
            {"id": "dart", "status": "active", "keys": ["DART_API_KEY"], "keep_raw": False},
        ]}
        tmp = Path(tempfile.mkdtemp()) / "sources.json"
        tmp.write_text(json.dumps(cfg), encoding="utf-8")

        fake = mock.Mock()
        fake.upsert_records.return_value = 1
        env = {"FRED_API_KEY": "T", "DART_API_KEY": "T"}
        with mock.patch.object(fred, "fetch", side_effect=RuntimeError("boom")), \
             mock.patch.object(dart, "fetch", return_value=dart_page(1, 1, 1, 1)):
            code = run.main(store=fake, config_path=tmp, env=env)

        self.assertEqual(code, 1)
        fake.set_error.assert_called_once()
        self.assertEqual(fake.set_error.call_args[0][0], "fred")
        fake.set_ok.assert_called_once_with("dart")

    def test_missing_key_is_recorded_as_failure(self):
        cfg = {"sources": [{"id": "fred", "status": "active", "keys": ["FRED_API_KEY"], "series": []}]}
        tmp = Path(tempfile.mkdtemp()) / "sources.json"
        tmp.write_text(json.dumps(cfg), encoding="utf-8")
        fake = mock.Mock()
        code = run.main(store=fake, config_path=tmp, env={})
        self.assertEqual(code, 1)
        self.assertIn("키 없음", fake.set_error.call_args[0][1])


class StoreTests(unittest.TestCase):
    def test_upsert_is_chunked_and_uses_conflict_key(self):
        items = [{"key": str(i), "observed_at": "2026-10-30", "payload": {"i": i}} for i in range(1200)]
        s = store_mod.SupabaseStore(url="https://example.supabase.co", key="TESTKEY")
        with mock.patch.object(store_mod, "request_json", return_value=None) as r:
            sent = s.upsert_records("index", "fred", items, raw_id=7)
        self.assertEqual(sent, 1200)
        self.assertEqual(r.call_count, 3)  # 500 + 500 + 200
        self.assertEqual(r.call_args_list[0][1]["params"], {"on_conflict": "source,key"})
        self.assertEqual(len(r.call_args_list[2][1]["body"]), 200)

    def test_key_is_sent_only_as_header(self):
        s = store_mod.SupabaseStore(url="https://example.supabase.co", key="TESTKEY")
        h = s._headers("return=minimal")
        self.assertEqual(h["apikey"], "TESTKEY")
        self.assertEqual(h["Authorization"], "Bearer TESTKEY")
        self.assertNotIn("TESTKEY", json.dumps(h.get("Prefer", "")))


if __name__ == "__main__":
    unittest.main()
