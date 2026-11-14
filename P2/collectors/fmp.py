"""FMP 일봉(EOD) 시세. 무료 플랜 (하루 250회, 미국 종목 위주).

문서: https://site.financialmodelingprep.com/developer/docs
무료 플랜에서 되는 엔드포인트만 쓴다. 2026-11-15 확인: SPY 일봉 조회 200 OK.
종목당 호출 1회. 유료 엔드포인트가 필요해지면 호출하지 말고 config에서 제외한다.
"""
from .net import get_json

BASE = "https://financialmodelingprep.com/stable/historical-price-eod/full"
KIND = "price"


def fetch(cfg, env):
    out = {}
    for sym in cfg.get("symbols", []):
        out[sym] = get_json(BASE, params={
            "symbol": sym,
            "limit": cfg.get("limit", 10),
            "apikey": env["FMP_API_KEY"],
        })
    return out


def normalize(raw, cfg):
    items = []
    for sym, rows in raw.items():
        if not isinstance(rows, list):
            continue  # 응답 형식이 목록이 아니면 그 종목은 건너뛴다
        for row in rows:
            day = row.get("date")
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
                    "source": "fmp",
                },
            })
    return items
