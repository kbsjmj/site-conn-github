"""DART 공시 목록 (준실시간). 문서: https://opendart.fss.or.kr/guide/main.do"""
from datetime import datetime, timedelta, timezone

from core.http import get_json

from .base import Adapter

URL = "https://opendart.fss.or.kr/api/list.json"
KST = timezone(timedelta(hours=9))
MAX_PAGES = 50  # page_count 100 기준 최대 5,000건 (2026-10-30 관측: 3일 조회 2,625건)


class DartAdapter(Adapter):
    name = "dart"
    kind = "disclosure"
    required_keys = ("DART_API_KEY",)

    def fetch(self, cfg, env):
        today = datetime.now(KST).date()
        start = today - timedelta(days=int(cfg.get("lookback_days", 3)))
        base = {
            "crtfc_key": env["DART_API_KEY"],
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": today.strftime("%Y%m%d"),
            "page_count": 100,
        }
        first = get_json(URL, params={**base, "page_no": 1})
        if first.get("status") != "000":
            return first  # 013(데이터 없음)이나 오류는 normalize가 판단한다
        items = list(first.get("list", []))
        total = int(first.get("total_page") or 1)
        last_page = min(total, MAX_PAGES)
        for page in range(2, last_page + 1):
            nxt = get_json(URL, params={**base, "page_no": page})
            if nxt.get("status") != "000":
                raise ValueError(
                    f"DART {page}페이지 상태 {nxt.get('status')}: {nxt.get('message', '')}")
            items.extend(nxt.get("list", []))
        merged = dict(first)
        merged["list"] = items
        merged["fetched_pages"] = last_page
        merged["truncated"] = total > MAX_PAGES  # 안전 상한에 걸리면 표시
        return merged

    def normalize(self, raw, cfg):
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


ADAPTER = DartAdapter()
