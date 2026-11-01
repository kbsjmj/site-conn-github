import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.storage import Store  # noqa: E402
from report import build, summary  # noqa: E402
from report.charts import change_bar_svg  # noqa: E402


def _idx(date, value, sym="SP500", name="S&P 500"):
    return {"key": f"{sym}:{date}", "observed_at": date,
            "payload": {"symbol": sym, "name": name, "date": date, "value": value, "unit": "points", "source": "fred"}}


class ReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = Store(self.root / "t.db")
        self.store.upsert_records("index", "fred", [_idx("2026-10-29", 1000.0), _idx("2026-10-30", 1010.0)])
        self.store.upsert_records("index", "fred", [_idx("2026-10-29", 3000.0, "DJIA", "Dow <Test>"),
                                                    _idx("2026-10-30", 2990.0, "DJIA", "Dow <Test>")])
        self.store.upsert_records("disclosure", "dart", [
            {"key": "1", "observed_at": "2026-10-30",
             "payload": {"rcept_no": "1", "corp_code": "0", "corp_name": "회사<A>", "report_nm": "공시 & 테스트",
                         "rcept_dt": "20261030", "url": "https://example.invalid/1"}}])

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_summary_change_percent(self):
        rows = {r["symbol"]: r for r in summary.index_changes(self.store)}
        self.assertAlmostEqual(1.0, rows["SP500"]["change_pct"])
        self.assertAlmostEqual(-0.33, rows["DJIA"]["change_pct"], places=2)

    def test_build_writes_html_and_manifest_with_escaping(self):
        res = build.build_daily(self.store, self.root / "out", tier=1)
        html = Path(res["html"]).read_text(encoding="utf-8")
        self.assertIn("+1.00%", html)
        self.assertIn("-0.33%", html)
        self.assertIn("Dow &lt;Test&gt;", html)     # 이름은 이스케이프된다
        self.assertIn("회사&lt;A&gt;", html)
        self.assertNotIn("{{", html)                  # 치환되지 않은 자리표시자가 없어야 한다
        self.assertIn("bar-pos", html)
        self.assertIn("bar-neg", html)
        import json
        manifest = json.loads((Path(res["dir"]) / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["tier"])
        self.assertEqual("2026-10-30", manifest["as_of"])

    def test_higher_tier_is_blocked_for_now(self):
        with self.assertRaises(NotImplementedError):
            build.build_daily(self.store, self.root / "out", tier=2)

    def test_chart_is_empty_without_rows(self):
        self.assertEqual("", change_bar_svg([]))


if __name__ == "__main__":
    unittest.main()
