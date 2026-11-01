"""NewsData.io 최신 기사. 문서: https://newsdata.io/documentation
무료 플랜은 일 크레딧이 작다. 기본 주기는 1800초이고, 10초 주기는 한도를 넘어서 쓰지 않는다 (공식 한도는 대시보드에서 확인)."""
from datetime import datetime, timedelta, timezone

from core.http import get_json

from .base import Adapter

URL = "https://newsdata.io/api/1/latest"
KST = timezone(timedelta(hours=9))
US = {"us", "united states of america"}
KR = {"kr", "south korea", "korea"}


class NewsDataAdapter(Adapter):
    name = "newsdata"
    kind = "news"
    required_keys = ("NEWSDATA_API_KEY",)

    def fetch(self, cfg, env):
        raw = get_json(URL, params={
            "apikey": env["NEWSDATA_API_KEY"],
            "country": cfg.get("country", "us,kr"),
            "category": cfg.get("category", "business"),
        })
        if raw.get("status") != "success":
            raise ValueError(f"NewsData 상태 {raw.get('status')}: {raw.get('message') or ''}")
        return raw

    def normalize(self, raw, cfg):
        items = []
        for a in raw.get("results") or []:
            link, title, pub, aid = a.get("link"), a.get("title"), a.get("pubDate"), a.get("article_id")
            if not (link and title and pub and aid):
                continue
            # NewsData의 pubDate는 UTC 기준이다
            published = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(KST)
            countries = {str(c).lower() for c in (a.get("country") or [])}
            region = "미국" if countries & US else ("국내" if countries & KR else "기타")
            items.append({
                "key": str(aid),
                "observed_at": published.date().isoformat(),
                "payload": {
                    "url": link,
                    "title": title,
                    "published_at": published.isoformat(timespec="seconds"),
                    "source": a.get("source_id") or "",
                    "summary": a.get("description") or "",
                    "region": region,
                    "query": cfg.get("category", "business"),
                },
            })
        return items


ADAPTER = NewsDataAdapter()
