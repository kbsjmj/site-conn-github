"""지수 등락률 계산. 같은 지수의 최신 두 관측값으로 전일 대비 변화를 구한다. 해석이나 전망은 하지 않는다."""


def index_changes(store, limit=2000):
    by_symbol = {}
    for r in store.latest("index", limit=limit):
        by_symbol.setdefault(r["payload"]["symbol"], []).append(r["payload"])
    out = []
    for sym, rows in by_symbol.items():
        rows = sorted(rows, key=lambda p: p["date"], reverse=True)
        if len(rows) < 2:
            continue  # 전일 값이 없으면 계산하지 않는다
        last, prev = rows[0], rows[1]
        if prev["value"] == 0:
            continue
        pct = (last["value"] / prev["value"] - 1) * 100
        out.append({
            "symbol": sym,
            "name": last.get("name", sym),
            "date": last["date"],
            "prev_date": prev["date"],
            "value": last["value"],
            "prev_value": prev["value"],
            "change_pct": round(pct, 2),
            "source": last.get("source", ""),
        })
    return sorted(out, key=lambda x: x["symbol"])
