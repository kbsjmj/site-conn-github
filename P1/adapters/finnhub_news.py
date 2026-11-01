"""Finnhub 시장 뉴스(general). 문서: https://finnhub.io/docs/api/market-news
무료 플랜은 분당 60회 한도다. 10초 주기(분당 6회)는 한도 안에 든다."""
from datetime import datetime, timedelta, timezone

from core.http import get_json

from .base import Adapter

URL = "https://finnhub.io/api/v1/news"
KST = timezone(timedelta(hours=9))


class FinnhubNewsAdapter(Adapter):
    name = "finnhub_news"
    kind = "news"
    required_keys = ("FINNHUB_API_KEY",)

    def fetch(self, cfg, env):
        return get_json(URL, params={
            "category": cfg.get("category", "general"),
            "token": env["FINNHUB_API_KEY"],
        })

    def normalize(self, raw, cfg):
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


ADAPTER = FinnhubNewsAdapter()
