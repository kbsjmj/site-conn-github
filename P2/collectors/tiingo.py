"""Tiingo 일봉 시세. 무료 플랜 (시간당 50회, 하루 1,000회, 월 1GB, 개인 내부용).

문서: https://api.tiingo.com/documentation/end-of-day
종목당 호출 1회. 인증은 Authorization 헤더로만 보낸다(주소에 키를 넣지 않는다).
"""
from datetime import date, timedelta

from .net import get_json

BASE = "https://api.tiingo.com/tiingo/daily/{sym}/prices"
KIND = "price"


def fetch(cfg, env):
    start = (date.today() - timedelta(days=cfg.get("lookback_days", 10))).isoformat()
    headers = {
        "Authorization": "Token " + env["TIINGO_API_KEY"],
        "Content-Type": "application/json",
    }
    out = {}
    for sym in cfg.get("symbols", []):
        out[sym] = get_json(BASE.format(sym=sym), params={"startDate": start},
                            headers=headers)
    return out


def normalize(raw, cfg):
    items = []
    for sym, rows in raw.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            ts = row.get("date") or ""
            day = ts[:10]  # "2026-11-13T00:00:00+00:00" -> "2026-11-13"
            close = row.get("close")
            if not day or close is None:
                continue
            items.append({
                "key": f"{sym}:{day}",
                "observed_at": day,
                "payload": {
                    "symbol": sym,
                    "date": day,
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": float(close),
                    "volume": row.get("volume"),
                    "currency": "USD",
                    "source": "tiingo",
                },
            })
    return items
