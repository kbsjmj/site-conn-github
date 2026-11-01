"""뉴스 어댑터와 실행 그룹 테스트. 모든 데이터는 합성값이고 네트워크를 쓰지 않는다."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from collectors import finnhub_news, naver_news, newsdata, run


class NewsdataTests(unittest.TestCase):
    def test_normalize_maps_region_and_date(self):
        raw = {"status": "success", "results": [{
            "article_id": "a1", "link": "https://example.com/1", "title": "합성 기사",
            "pubDate": "2026-11-01 00:00:00", "country": ["kr"], "source_id": "exsrc",
            "description": "요약",
        }]}
        items = newsdata.normalize(raw, {"category": "business"})
        self.assertEqual(items[0]["key"], "a1")
        self.assertEqual(items[0]["observed_at"], "2026-11-01")  # UTC 00:00 = KST 09:00
        self.assertEqual(items[0]["payload"]["region"], "국내")

    def test_fetch_raises_on_non_success(self):
        with mock.patch.object(newsdata, "get_json", return_value={"status": "error", "message": "limit"}):
            with self.assertRaisesRegex(ValueError, "NewsData 상태 error"):
                newsdata.fetch({}, {"NEWSDATA_API_KEY": "T"})


class NaverTests(unittest.TestCase):
    def test_normalize_strips_tags_and_uses_link_as_key(self):
        raw = {"증시": {"items": [{
            "title": "<b>증시</b> &amp; 상승", "link": "https://n.news/1",
            "originallink": "https://www.khan.co.kr/a", "pubDate": "Sat, 31 Oct 2026 21:00:00 +0900",
            "description": "<b>요약</b>",
        }]}}
        items = naver_news.normalize(raw, {})
        self.assertEqual(items[0]["key"], "https://n.news/1")
        self.assertEqual(items[0]["payload"]["title"], "증시 & 상승")
        self.assertEqual(items[0]["payload"]["source"], "khan.co.kr")
        self.assertEqual(items[0]["payload"]["summary"], "요약")

    def test_fetch_queries_every_keyword(self):
        body = {"items": []}
        with mock.patch.object(naver_news, "get_json", return_value=body) as g:
            out = naver_news.fetch({"queries": ["증시", "금리"]},
                                   {"NAVER_API_KEY_ID": "I", "NAVER_API_KEY": "S"})
        self.assertEqual(set(out), {"증시", "금리"})
        self.assertEqual(g.call_count, 2)

    def test_error_code_raises(self):
        with mock.patch.object(naver_news, "get_json", return_value={"errorCode": "024", "errorMessage": "인증 실패"}):
            with self.assertRaisesRegex(ValueError, "024"):
                naver_news.fetch({"queries": ["증시"]}, {"NAVER_API_KEY_ID": "I", "NAVER_API_KEY": "S"})


class FinnhubNewsTests(unittest.TestCase):
    def test_normalize_uses_id_as_key(self):
        raw = [{"id": 900001, "url": "https://example.com/f", "headline": "합성 헤드라인",
                "datetime": 1793448000, "source": "src", "summary": "s"}]
        items = finnhub_news.normalize(raw, {"category": "general"})
        self.assertEqual(items[0]["key"], "900001")
        self.assertEqual(items[0]["payload"]["region"], "미국")

    def test_non_list_response_raises(self):
        with self.assertRaisesRegex(ValueError, "형식 오류"):
            finnhub_news.normalize({"error": "x"}, {})


class GroupTests(unittest.TestCase):
    def _config(self):
        cfg = {"sources": [
            {"id": "fred", "status": "active", "schedule": "daily", "keys": ["FRED_API_KEY"], "keep_raw": False, "series": []},
            {"id": "newsdata", "status": "active", "schedule": "news", "keys": ["NEWSDATA_API_KEY"], "keep_raw": False},
        ]}
        path = Path(tempfile.mkdtemp()) / "sources.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return path

    def test_news_group_runs_only_news_sources(self):
        fake = mock.Mock()
        fake.upsert_records.return_value = 0
        env = {"FRED_API_KEY": "T", "NEWSDATA_API_KEY": "T"}
        with mock.patch.object(run.fred, "fetch") as f, \
             mock.patch.object(run.newsdata, "fetch", return_value={"status": "success", "results": []}) as n:
            code = run.main(store=fake, config_path=self._config(), env=env, group="news")
        self.assertEqual(code, 0)
        f.assert_not_called()
        n.assert_called_once()

    def test_daily_group_skips_news(self):
        fake = mock.Mock()
        fake.upsert_records.return_value = 0
        env = {"FRED_API_KEY": "T", "NEWSDATA_API_KEY": "T"}
        with mock.patch.object(run.fred, "fetch", return_value={}) as f, \
             mock.patch.object(run.newsdata, "fetch") as n:
            run.main(store=fake, config_path=self._config(), env=env, group="daily")
        f.assert_called_once()
        n.assert_not_called()


if __name__ == "__main__":
    unittest.main()
