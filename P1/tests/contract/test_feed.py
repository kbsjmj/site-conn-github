import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.storage import Store  # noqa: E402
from server.feed import news_payload, poll_sec  # noqa: E402


def _items(n):
    return [{
        "key": f"k{i}",
        "observed_at": "2026-10-31",
        "payload": {"url": f"https://example.com/{i}", "title": f"합성 {i}",
                    "published_at": "2026-10-31T12:00:00+09:00", "source": "synthetic",
                    "summary": "", "region": "국내", "query": "증시"},
    } for i in range(n)]


class NewsPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_first_page_is_oldest_first_and_incremental_after_cursor(self):
        self.store.upsert_records("news", "naver_news", _items(3))
        first = news_payload(self.store, {"naver_news"})
        self.assertEqual(["합성 0", "합성 1", "합성 2"], [i["title"] for i in first["items"]])
        cursor = first["last_seq"]
        self.store.upsert_records("news", "naver_news", _items(4))  # k0~k2 갱신, k3 신규
        nxt = news_payload(self.store, {"naver_news"}, after=cursor)
        self.assertEqual(["합성 3"], [i["title"] for i in nxt["items"]])
        self.assertGreater(nxt["last_seq"], cursor)

    def test_no_new_items_keeps_cursor(self):
        self.store.upsert_records("news", "naver_news", _items(2))
        cursor = news_payload(self.store, {"naver_news"})["last_seq"]
        nxt = news_payload(self.store, {"naver_news"}, after=cursor)
        self.assertEqual([], nxt["items"])
        self.assertEqual(cursor, nxt["last_seq"])

    def test_status_limited_to_news_sources(self):
        self.store.set_status_ok("naver_news")
        self.store.set_status_ok("dart")
        ids = [s["source"] for s in news_payload(self.store, {"naver_news"})["status"]]
        self.assertEqual(["naver_news"], ids)

    def test_poll_sec_defaults_to_interval(self):
        class S:
            extra = {}
            interval_min = 2
        self.assertEqual(120, poll_sec(S()))
        S.extra = {"poll_sec": 10}
        self.assertEqual(10, poll_sec(S()))


if __name__ == "__main__":
    unittest.main()
