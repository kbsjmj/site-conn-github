"""네이버 뉴스 검색. 조회 키워드를 poll마다 순환한다 (쿼터 보호).
주의: NAVER_API_KEY_ID / NAVER_API_KEY를 검색 API의 Client ID / Client Secret으로 가정한다.
NCP API HUB 키 형식이 다르면 Mac에서 `run --source naver_news`로 확인하고 헤더를 고친다."""
import html
import re
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from core.http import get_json

from .base import Adapter

URL = "https://openapi.naver.com/v1/search/news.json"
KST = timezone(timedelta(hours=9))
TAG = re.compile(r"<[^>]+>")


def _clean(text):
    return html.unescape(TAG.sub("", text or "")).strip()


class NaverNewsAdapter(Adapter):
    name = "naver_news"
    kind = "news"
    required_keys = ("NAVER_API_KEY_ID", "NAVER_API_KEY")

    def fetch(self, cfg, env):
        queries = cfg.get("queries") or ["증시"]
        query = queries[int(cfg.get("_tick", 0)) % len(queries)]
        raw = get_json(URL, params={
            "query": query,
            "display": int(cfg.get("display", 20)),
            "sort": "date",
        }, headers={
            "X-Naver-Client-Id": env["NAVER_API_KEY_ID"],
            "X-Naver-Client-Secret": env["NAVER_API_KEY"],
        })
        if "errorCode" in raw:
            raise ValueError(f"네이버 응답 오류 {raw.get('errorCode')}: {raw.get('errorMessage', '')}")
        raw["_query"] = query
        return raw

    def normalize(self, raw, cfg):
        items = []
        for it in raw.get("items", []):
            link = it.get("link") or it.get("originallink")
            title = _clean(it.get("title"))
            if not (link and title and it.get("pubDate")):
                continue
            published = parsedate_to_datetime(it["pubDate"]).astimezone(KST)
            items.append({
                "key": link,
                "observed_at": published.date().isoformat(),
                "payload": {
                    "url": it.get("originallink") or link,
                    "title": title,
                    "published_at": published.isoformat(timespec="seconds"),
                    "source": urlparse(it.get("originallink") or link).netloc.removeprefix("www."),
                    "summary": _clean(it.get("description")),
                    "region": "국내",
                    "query": raw.get("_query", ""),
                },
            })
        return items


ADAPTER = NaverNewsAdapter()
