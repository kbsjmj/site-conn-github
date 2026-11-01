"""FRED 시계열 (미국 지수 일별 종가). 문서: https://fred.stlouisfed.org/docs/api/fred/series_observations.html"""
from .net import get_json

BASE = "https://api.stlouisfed.org/fred/series/observations"
KIND = "index"
NAMES = {
    "SP500": "S&P 500",
    "NASDAQCOM": "NASDAQ Composite",
    "DJIA": "Dow Jones Industrial Average",
}


def fetch(cfg, env):
    out = {}
    for sid in cfg.get("series", []):
        out[sid] = get_json(BASE, params={
            "series_id": sid,
            "api_key": env["FRED_API_KEY"],
            "file_type": "json",
            "sort_order": "desc",
            "limit": cfg.get("limit", 10),
        })
    return out


def normalize(raw, cfg):
    items = []
    for sid, body in raw.items():
        for ob in body.get("observations", []):
            value = ob.get("value")
            if value in (None, ".", ""):
                continue  # FRED는 결측을 "."으로 준다
            date = ob["date"]
            items.append({
                "key": f"{sid}:{date}",
                "observed_at": date,
                "payload": {
                    "symbol": sid,
                    "name": NAMES.get(sid, sid),
                    "date": date,
                    "value": float(value),
                    "unit": "points",
                    "source": "fred",
                },
            })
    return items
