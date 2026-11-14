"""교차검증: 같은 종목·같은 날짜의 종가를 소스끼리 비교한다.

- 두 소스 이상 값이 있으면 최고·최저 차이(%)를 계산한다. 허용 오차 안이면 "일치", 넘으면 "불일치".
- 어느 값이 맞는지 자동으로 고르지 않는다. 두 값을 모두 기록한다.
- 한 소스만 값이 있으면 "단일소스"로 남긴다 (비교 불가이지 오류가 아니다).
"""

TOLERANCE = 0.005  # 0.5%


def compare(by_source, tolerance=TOLERANCE):
    """by_source: {"fmp": {("SPY", "2026-11-13"): 754.37, ...}, "tiingo": {...}}
    반환: store.upsert_records에 넣을 items 목록."""
    keys = set()
    for values in by_source.values():
        keys.update(values.keys())

    items = []
    for sym, day in sorted(keys):
        vals = {s: by_source[s][(sym, day)] for s in sorted(by_source) if (sym, day) in by_source[s]}
        if len(vals) < 2:
            status, diff_pct = "단일소스", None
        else:
            lo, hi = min(vals.values()), max(vals.values())
            diff_pct = round((hi - lo) / lo * 100, 4) if lo else None
            status = "일치" if diff_pct is not None and diff_pct <= tolerance * 100 else "불일치"
        items.append({
            "key": f"{sym}:{day}",
            "observed_at": day,
            "payload": {
                "symbol": sym,
                "date": day,
                "values": vals,
                "diff_pct": diff_pct,
                "status": status,
                "tolerance_pct": tolerance * 100,
                "source": "cross_check",
            },
        })
    return items
