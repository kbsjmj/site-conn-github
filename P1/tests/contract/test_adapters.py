import json
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import registry  # noqa: E402
from adapters.dart import ADAPTER as DART  # noqa: E402
from adapters.fred import ADAPTER as FRED  # noqa: E402
from adapters.finnhub_news import ADAPTER as FINNHUB_NEWS  # noqa: E402
from adapters.naver_news import ADAPTER as NAVER_NEWS  # noqa: E402
from adapters.newsdata import ADAPTER as NEWSDATA  # noqa: E402
from unittest import mock  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load(path):
    return json.loads((FIX / path).read_text(encoding="utf-8"))


class AdapterContractTest(unittest.TestCase):
    """등록된 모든 어댑터가 지켜야 할 공통 규칙."""

    def test_every_adapter_kind_is_registered(self):
        kinds = registry.load_kinds()
        for name, adapter in registry.discover_adapters().items():
            self.assertIn(adapter.kind, kinds, f"{name}: kinds.yaml에 없는 종류")
            self.assertEqual(name, adapter.name, f"{name}: name이 모듈 이름과 다름")

    def _check_items(self, adapter_kind, items):
        kinds = registry.load_kinds()
        required = kinds[adapter_kind]["required"]
        keys = [it["key"] for it in items]
        self.assertEqual(len(keys), len(set(keys)), "key 중복")
        for it in items:
            self.assertEqual({"key", "observed_at", "payload"}, set(it.keys()))
            self.assertRegex(it["observed_at"], DATE)
            for f in required:
                self.assertIn(f, it["payload"], f"필수 필드 누락: {f}")
                self.assertNotIn(it["payload"][f], (None, ""))


class FredAdapterTest(AdapterContractTest):
    def test_normalize_skips_missing_values_and_keeps_contract(self):
        raw = _load("fred/raw.json")
        items = FRED.normalize(raw, {})
        self.assertEqual(6, len(items))  # SP500 2(결측 1 제외) + NASDAQ 2 + DJIA 2
        self._check_items("index", items)
        sp = [i for i in items if i["payload"]["symbol"] == "SP500"]
        self.assertEqual({"2026-10-30", "2026-10-29"}, {i["payload"]["date"] for i in sp})
        self.assertIsInstance(sp[0]["payload"]["value"], float)


class DartAdapterTest(AdapterContractTest):
    def test_normalize_disclosures(self):
        raw = _load("dart/raw.json")
        items = DART.normalize(raw, {})
        self.assertEqual(2, len(items))
        self._check_items("disclosure", items)
        self.assertEqual("2026-10-30", items[0]["observed_at"])
        self.assertIn("rcpNo=20261030000001", items[0]["payload"]["url"])

    def test_no_data_status_returns_empty(self):
        self.assertEqual([], DART.normalize(_load("dart/raw_none.json"), {}))

    def test_error_status_raises(self):
        with self.assertRaises(ValueError):
            DART.normalize({"status": "010", "message": "등록되지 않은 키"}, {})


class DartPaginationTest(AdapterContractTest):
    def _item(self, n):
        return {"rcept_no": f"2026103000{n:04d}", "rcept_dt": "20261030",
                "corp_code": "00126380", "corp_name": "테스트", "stock_code": "005930",
                "report_nm": "사업보고서", "flr_nm": "테스트"}

    def test_fetch_collects_every_page(self):
        pages = {
            1: {"status": "000", "total_page": 3, "list": [self._item(1)]},
            2: {"status": "000", "total_page": 3, "list": [self._item(2)]},
            3: {"status": "000", "total_page": 3, "list": [self._item(3)]},
        }
        calls = []

        def fake(url, params=None, **kw):
            calls.append(params["page_no"])
            return pages[params["page_no"]]

        with mock.patch("adapters.dart.get_json", side_effect=fake):
            raw = DART.fetch({}, {"DART_API_KEY": "test-key"})
        self.assertEqual([1, 2, 3], calls)
        items = DART.normalize(raw, {})
        self.assertEqual(3, len(items))
        self._check_items("disclosure", items)
        self.assertFalse(raw["truncated"])

    def test_later_page_error_raises(self):
        pages = {
            1: {"status": "000", "total_page": 2, "list": [self._item(1)]},
            2: {"status": "010", "message": "사용한도 초과"},
        }
        with mock.patch("adapters.dart.get_json", side_effect=lambda u, params=None, **k: pages[params["page_no"]]):
            with self.assertRaises(ValueError):
                DART.fetch({}, {"DART_API_KEY": "test-key"})


class NewsAdapterTest(AdapterContractTest):
    def test_finnhub_news(self):
        items = FINNHUB_NEWS.normalize(_load("finnhub_news/raw.json"), {})
        self.assertEqual(2, len(items))
        self._check_items("news", items)
        self.assertEqual("미국", items[0]["payload"]["region"])
        self.assertEqual("2026-10-31", items[0]["observed_at"])

    def test_naver_news_strips_tags_and_unescapes(self):
        raw = _load("naver_news/raw.json")
        raw["_query"] = "증시"
        items = NAVER_NEWS.normalize(raw, {})
        self.assertEqual(2, len(items))
        self._check_items("news", items)
        self.assertEqual('[합성] 증시 마감 "요약"', items[0]["payload"]["title"])
        self.assertEqual("국내", items[0]["payload"]["region"])
        self.assertEqual("2026-10-31T20:30:00+09:00", items[0]["payload"]["published_at"])
        self.assertEqual("증시", items[0]["payload"]["query"])

    def test_naver_news_rotates_queries_per_tick(self):
        cfg = {"queries": ["가", "나"], "_tick": 3}
        env = {"NAVER_API_KEY_ID": "id-test", "NAVER_API_KEY": "secret-test"}
        with mock.patch("adapters.naver_news.get_json", return_value={"items": []}) as gj:
            NAVER_NEWS.fetch(cfg, env)
        self.assertEqual("나", gj.call_args.kwargs["params"]["query"])  # 3 % 2 = 1
        self.assertEqual("secret-test", gj.call_args.kwargs["headers"]["X-Naver-Client-Secret"])

    def test_newsdata_region_and_utc_to_kst(self):
        items = NEWSDATA.normalize(_load("newsdata/raw.json"), {})
        self.assertEqual(2, len(items))
        self._check_items("news", items)
        self.assertEqual(["미국", "국내"], [i["payload"]["region"] for i in items])
        self.assertEqual("2026-10-31T15:00:00+09:00", items[0]["payload"]["published_at"])


if __name__ == "__main__":
    unittest.main()
