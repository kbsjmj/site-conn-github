import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.storage import Store  # noqa: E402


def _item(key, date, value):
    return {"key": key, "observed_at": date,
            "payload": {"symbol": "SP500", "date": date, "value": value, "name": "S&P 500", "source": "fred"}}


class StorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_upsert_is_idempotent_and_keeps_seq(self):
        items = [_item("SP500:2026-10-29", "2026-10-29", 1000.0), _item("SP500:2026-10-30", "2026-10-30", 1010.0)]
        self.assertEqual((2, 0), self.store.upsert_records("index", "fred", items))
        before = self.store.after("index", 0, 10)
        self.assertEqual((0, 2), self.store.upsert_records("index", "fred", items))
        after = self.store.after("index", 0, 10)
        self.assertEqual([r["seq"] for r in before], [r["seq"] for r in after])

    def test_after_pages_by_seq(self):
        items = [_item(f"SP500:2026-10-{d:02d}", f"2026-10-{d:02d}", float(d)) for d in range(1, 6)]
        self.store.upsert_records("index", "fred", items)
        first = self.store.after("index", 0, 2)
        self.assertEqual(2, len(first))
        rest = self.store.after("index", first[-1]["seq"], 10)
        self.assertEqual(3, len(rest))
        self.assertTrue(all(r["seq"] > first[-1]["seq"] for r in rest))

    def test_status_error_counts_and_masks_nothing_extra(self):
        self.store.set_status_error("fred", "HTTP 401")
        self.store.set_status_error("fred", "HTTP 401")
        st = {r["source"]: r for r in self.store.statuses()}["fred"]
        self.assertEqual(2, st["consecutive_failures"])
        self.store.set_status_ok("fred")
        st = {r["source"]: r for r in self.store.statuses()}["fred"]
        self.assertEqual(0, st["consecutive_failures"])


if __name__ == "__main__":
    unittest.main()
