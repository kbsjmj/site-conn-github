"""네이버 뉴스 검색. 설정된 키워드마다 한 번씩 호출한다 (뉴스 그룹, 30분 주기).
NAVER_API_KEY_ID / NAVER_API_KEY를 검색 API의 Client ID / Client Secret으로 가정한다.
NCP API HUB 키 형식이 다르면 인증 헤더를 고쳐야 한다 (실패 메시지로 확인)."""
import html
import re
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .net import get_json

URL = "https://openapi.naver.com/v1/search/news.json"
KIND = "news"
KST = timezone(timedelta(hours=9))
TAG = re.compile(r"<[^>]+>")


def _clean(text):
    return html.unescape(TAG.sub("", text or "")).strip()


def fetch(cfg, env):
    headers = {
        "X-Naver-Client-Id": env["NAVER_API_KEY_ID"],
        "X-Naver-Client-Secret": env["NAVER_API_KEY"],
    }
    out = {}
    for query in cfg.get("queries") or ["증시"]:
        raw = get_json(URL, params={
            "query": query,
            "display": int(cfg.get("display", 20)),
            "sort": "date",
        }, headers=headers)
        if "errorCode" in raw:
            raise ValueError(f"네이버 응답 오류 {raw.get('errorCode')}: {raw.get('errorMessage', '')}")
        out[query] = raw
    return out


def normalize(raw, cfg):
    items = []
    for query, body in raw.items():
        for it in body.get("items", []):
            link = it.get("link") or it.get("originallink")
            title = _clean(it.get("title"))
            if not (link and title and it.get("pubDate")):
                continue
            published = parsedate_to_datetime(it["pubDate"]).astimezone(KST)
            origin = it.get("originallink") or link
            items.append({
                "key": link,
                "observed_at": published.date().isoformat(),
                "payload": {
                    "url": origin,
                    "title": title,
                    "published_at": published.isoformat(timespec="seconds"),
                    "source": urlparse(origin).netloc.removeprefix("www."),
                    "summary": _clean(it.get("description")),
                    "region": "국내",
                    "query": query,
                },
            })
    return items
