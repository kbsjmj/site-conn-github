"""Finnhub 시장 뉴스(general). 문서: https://finnhub.io/docs/api/market-news
뉴스 그룹은 30분마다 한 번 호출한다. 무료 플랜 한도(분당 60회)보다 훨씬 적다."""
from datetime import datetime, timedelta, timezone

from .net import get_json

URL = "https://finnhub.io/api/v1/news"
KIND = "news"
KST = timezone(timedelta(hours=9))


def fetch(cfg, env):
    return get_json(URL, params={
        "category": cfg.get("category", "general"),
        "token": env["FINNHUB_API_KEY"],
    })


def normalize(raw, cfg):
    if not isinstance(raw, list):
        raise ValueError(f"Finnhub 응답 형식 오류: {type(raw).__name__}")
    items = []
    for it in raw:
        url, title, ts = it.get("url"), it.get("headline"), it.get("datetime")
        if not (url and title and ts):
            continue
        published = datetime.fromtimestamp(int(ts), tz=KST)
        items.append({
            "key": str(it.get("id") or url),
            "observed_at": published.date().isoformat(),
            "payload": {
                "url": url,
                "title": title,
                "published_at": published.isoformat(timespec="seconds"),
                "source": it.get("source") or "",
                "summary": it.get("summary") or "",
                "region": "미국",
                "query": cfg.get("category", "general"),
            },
        })
    return items
