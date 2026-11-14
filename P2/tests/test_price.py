"""시세 어댑터(FMP, Tiingo)와 교차검증 테스트. 모든 데이터는 합성값이고 네트워크를 쓰지 않는다."""
import unittest
from unittest import mock

from collectors import fmp, tiingo, validate


FMP_ROWS = [
    {"symbol": "SPY", "date": "2026-11-13", "open": 760.0, "high": 761.0, "low": 747.0,
     "close": 754.37, "volume": 100},
    {"symbol": "SPY", "date": "2026-11-12", "open": 758.0, "high": 762.0, "low": 750.0,
     "close": 759.80, "volume": 90},
]
TIINGO_ROWS = [
    {"date": "2026-11-13T00:00:00+00:00", "open": 760.0, "high": 761.0, "low": 747.0,
     "close": 754.37, "volume": 100},
]


class FmpTests(unittest.TestCase):
    def test_normalize_builds_keys_and_source(self):
        items = fmp.normalize({"SPY": FMP_ROWS}, {})
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["key"], "SPY:2026-11-13")
        self.assertEqual(items[0]["payload"]["source"], "fmp")
        self.assertEqual(items[0]["payload"]["close"], 754.37)

    def test_normalize_skips_bad_rows(self):
        raw = {"SPY": [{"date": "2026-11-13", "close": None}], "QQQ": {"error": "x"}}
        self.assertEqual(fmp.normalize(raw, {}), [])

    def test_fetch_sends_key_in_params_only_once_per_symbol(self):
        with mock.patch.object(fmp, "get_json", return_value=FMP_ROWS) as gj:
            raw = fmp.fetch({"symbols": ["SPY", "QQQ"], "limit": 5}, {"FMP_API_KEY": "K"})
        self.assertEqual(set(raw), {"SPY", "QQQ"})
        self.assertEqual(gj.call_count, 2)
        self.assertEqual(gj.call_args.kwargs["params"]["limit"], 5)


class TiingoTests(unittest.TestCase):
    def test_normalize_cuts_timestamp_to_date(self):
        items = tiingo.normalize({"SPY": TIINGO_ROWS}, {})
        self.assertEqual(items[0]["key"], "SPY:2026-11-13")
        self.assertEqual(items[0]["payload"]["source"], "tiingo")

    def test_fetch_puts_token_in_header_not_url(self):
        with mock.patch.object(tiingo, "get_json", return_value=TIINGO_ROWS) as gj:
            tiingo.fetch({"symbols": ["SPY"], "lookback_days": 10}, {"TIINGO_API_KEY": "SECRET"})
        url = gj.call_args.args[0]
        headers = gj.call_args.kwargs["headers"]
        self.assertNotIn("SECRET", url)
        self.assertEqual(headers["Authorization"], "Token SECRET")


class ValidateTests(unittest.TestCase):
    def test_agreement_within_tolerance(self):
        by = {"fmp": {("SPY", "2026-11-13"): 754.37},
              "tiingo": {("SPY", "2026-11-13"): 754.40}}
        (item,) = validate.compare(by)
        self.assertEqual(item["payload"]["status"], "일치")
        self.assertEqual(item["key"], "SPY:2026-11-13")

    def test_disagreement_is_flagged_not_resolved(self):
        by = {"fmp": {("SPY", "2026-11-13"): 754.37},
              "tiingo": {("SPY", "2026-11-13"): 740.00}}
        (item,) = validate.compare(by)
        self.assertEqual(item["payload"]["status"], "불일치")
        self.assertEqual(item["payload"]["values"], {"fmp": 754.37, "tiingo": 740.0})  # 둘 다 기록

    def test_single_source_is_not_an_error(self):
        by = {"fmp": {("SPY", "2026-11-13"): 754.37}, "tiingo": {}}
        (item,) = validate.compare(by)
        self.assertEqual(item["payload"]["status"], "단일소스")
        self.assertIsNone(item["payload"]["diff_pct"])


if __name__ == "__main__":
    unittest.main()
