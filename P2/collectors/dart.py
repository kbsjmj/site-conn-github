"""DART 공시 목록. 문서: https://opendart.fss.or.kr/guide/main.do

2026-10-30 점검 결과 page_count 100으로 3일 조회 시 2,625건이었다.
이전 프로토타입은 1페이지(100건)만 가져와서 2,525건이 빠졌다. 이 버전은 전 페이지를 받고,
받은 건수가 total_count와 다르면 실패로 처리해 조용히 일부만 저장되지 않도록 한다.
"""
from datetime import datetime, timedelta, timezone

from .net import get_json

URL = "https://opendart.fss.or.kr/api/list.json"
KIND = "disclosure"
KST = timezone(timedelta(hours=9))
PAGE_COUNT = 100
MAX_PAGES = 50  # 100건 x 50페이지 = 5,000건. 넘으면 lookback_days를 줄인다.


def fetch(cfg, env):
    today = datetime.now(KST).date()
    start = today - timedelta(days=int(cfg.get("lookback_days", 3)))
    base = {
        "crtfc_key": env["DART_API_KEY"],
        "bgn_de": start.strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"),
        "page_count": PAGE_COUNT,
    }
    first = get_json(URL, params={**base, "page_no": 1})
    if first.get("status") != "000":
        return first  # 013(데이터 없음)이나 오류는 normalize가 판단한다

    total_pages = int(first.get("total_page") or 1)
    if total_pages > MAX_PAGES:
        raise ValueError(f"DART 페이지 {total_pages}개가 안전 상한 {MAX_PAGES}을 넘었습니다. lookback_days를 줄이세요.")

    items = list(first.get("list", []))
    for page in range(2, total_pages + 1):
        nxt = get_json(URL, params={**base, "page_no": page})
        if nxt.get("status") != "000":
            raise ValueError(f"DART {page}페이지 상태 {nxt.get('status')}: {nxt.get('message', '')}")
        items.extend(nxt.get("list", []))

    expected = int(first.get("total_count") or len(items))
    if len(items) != expected:
        raise ValueError(f"DART 건수 불일치: 받은 {len(items)}건, 전체 {expected}건")

    return {**first, "list": items, "fetched_pages": total_pages}


def normalize(raw, cfg):
    status = raw.get("status")
    if status == "013":  # 조회된 데이터 없음
        return []
    if status != "000":
        raise ValueError(f"DART 응답 상태 {status}: {raw.get('message', '')}")
    items = []
    for it in raw.get("list", []):
        d = it["rcept_dt"]
        items.append({
            "key": it["rcept_no"],
            "observed_at": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "payload": {
                "rcept_no": it["rcept_no"],
                "corp_code": it.get("corp_code"),
                "corp_name": it.get("corp_name"),
                "stock_code": it.get("stock_code"),
                "report_nm": it.get("report_nm"),
                "rcept_dt": d,
                "flr_nm": it.get("flr_nm"),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it['rcept_no']}",
            },
        })
    return items
