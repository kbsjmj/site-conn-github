"""NewsData.io 최신 기사. 문서: https://newsdata.io/documentation
무료 플랜은 일 크레딧이 작다. 뉴스 그룹은 30분마다 한 번씩 호출한다 (하루 48회)."""
from datetime import datetime, timedelta, timezone

from .net import get_json

URL = "https://newsdata.io/api/1/latest"
KIND = "news"
KST = timezone(timedelta(hours=9))
US = {"us", "united states of america"}
KR = {"kr", "south korea", "korea"}


def fetch(cfg, env):
    raw = get_json(URL, params={
        "apikey": env["NEWSDATA_API_KEY"],
        "country": cfg.get("country", "us,kr"),
        "category": cfg.get("category", "business"),
    })
    if raw.get("status") != "success":
        raise ValueError(f"NewsData 상태 {raw.get('status')}: {raw.get('message') or ''}")
    return raw


def normalize(raw, cfg):
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
