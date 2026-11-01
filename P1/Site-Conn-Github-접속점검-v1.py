#!/usr/bin/env python3
"""Site-Conn-Github 접속 점검 v1

소스별 호스트에 HTTPS 요청을 보내 접속 가능 여부를 판정한다.
- 외부 패키지 없이 표준 라이브러리만 사용
- API 키는 쓰지 않는다 (키 없이 응답하는 상태 코드로만 판정)

판정 기준
- 연결 실패/타임아웃/DNS 실패 : 접속 불가
- 200~399                      : 접속 가능
- 401/403                      : 접속 가능 (키 또는 승인 필요)
- 404/405 등 그 외 HTTP 응답    : 접속 가능 (엔드포인트 확인 필요)

사용법
  python3 Site-Conn-Github-접속점검-v1.py
  python3 Site-Conn-Github-접속점검-v1.py --csv 결과.csv
"""
import argparse
import csv
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# (구분, 소스명, 점검 URL)
TARGETS = [
    ("해외 시세/재무", "Alpha Vantage", "https://www.alphavantage.co/query"),
    ("해외 시세/재무", "Finnhub", "https://finnhub.io/api/v1/quote"),
    ("해외 시세/재무", "Polygon.io", "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-05"),
    ("해외 시세/재무", "FMP", "https://financialmodelingprep.com/api/v3/profile/AAPL"),
    ("해외 시세/재무", "Yahoo Finance (비공식 엔드포인트)", "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"),
    ("해외 시세/재무", "Tiingo", "https://api.tiingo.com/api/test"),
    ("해외 거시", "FRED", "https://api.stlouisfed.org/fred/series?series_id=GDP"),
    ("국내 공시", "DART", "https://opendart.fss.or.kr/api/list.json"),
    ("국내 거시", "한국은행 ECOS", "https://ecos.bok.or.kr/api/StatisticSearch"),
    ("국내 공공", "공공데이터포털", "https://www.data.go.kr"),
    ("국내 시세", "KRX (open)", "https://open.krx.co.kr"),
    ("국내 시세", "KRX (data)", "https://data.krx.co.kr"),
    ("증권사 API", "한국투자증권", "https://openapi.koreainvestment.com:9443"),
    ("증권사 API", "미래에셋증권", "https://openapi.miraeasset.com"),
    ("뉴스", "네이버 뉴스 검색", "https://openapi.naver.com/v1/search/news.json"),
    ("뉴스", "NewsData.io", "https://newsdata.io/api/1/latest"),
    ("뉴스", "Currents API", "https://api.currentsapi.services/v1/latest-news"),
    ("뉴스", "NewsAPI.org", "https://newsapi.org/v2/top-headlines"),
    ("뉴스", "The Guardian", "https://content.guardianapis.com/search"),
]

USER_AGENT = "Site-Conn-Github-probe/1.0"


def probe(url, timeout):
    """(판정, 상태코드 또는 None, 소요 ms, 비고) 을 반환."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            resp.read(256)
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except urllib.error.URLError as e:
        reason = e.reason
        ms = int((time.monotonic() - started) * 1000)
        if isinstance(reason, socket.gaierror):
            return "접속 불가", None, ms, "DNS 실패"
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "접속 불가", None, ms, "타임아웃"
        return "접속 불가", None, ms, f"연결 오류: {reason}"
    except (socket.timeout, TimeoutError):
        ms = int((time.monotonic() - started) * 1000)
        return "접속 불가", None, ms, "타임아웃"
    except Exception as e:  # 예상 밖 오류도 기록만 하고 계속 진행
        ms = int((time.monotonic() - started) * 1000)
        return "접속 불가", None, ms, f"예외: {type(e).__name__}"

    ms = int((time.monotonic() - started) * 1000)
    if 200 <= code < 400:
        return "접속 가능", code, ms, "정상 응답"
    if code in (401, 403):
        return "접속 가능", code, ms, "키 또는 승인 필요"
    return "접속 가능", code, ms, "엔드포인트 확인 필요"


def main():
    parser = argparse.ArgumentParser(description="금융 API 접속 점검")
    parser.add_argument("--timeout", type=float, default=10.0, help="요청당 제한 시간(초)")
    parser.add_argument("--csv", help="결과를 저장할 CSV 경로")
    args = parser.parse_args()

    print(f"점검 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (로컬 시간)")
    print(f"대상 {len(TARGETS)}개, 제한 시간 {args.timeout:.0f}초\n")
    header = f"{'구분':<14}{'소스':<28}{'판정':<10}{'코드':<6}{'ms':>7}  비고"
    print(header)
    print("-" * len(header))

    rows = []
    for group, name, url in TARGETS:
        verdict, code, ms, note = probe(url, args.timeout)
        code_s = str(code) if code is not None else "-"
        print(f"{group:<14}{name:<28}{verdict:<10}{code_s:<6}{ms:>7}  {note}")
        rows.append([group, name, url, verdict, code_s, ms, note])

    ok = sum(1 for r in rows if r[3] == "접속 가능")
    print(f"\n요약: 접속 가능 {ok} / 접속 불가 {len(rows) - ok}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["구분", "소스", "URL", "판정", "HTTP코드", "소요ms", "비고"])
            w.writerows(rows)
        print(f"CSV 저장: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
