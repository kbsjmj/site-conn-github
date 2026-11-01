"""수집·제공 프로그램 진입점.

사용법:
  python3 main.py                  인자 없음: 활성 소스 수집 → 지수 요약 → 보고서 (일괄 실행)
  python3 main.py sources          소스 등록부와 유효 상태 (키 값은 표시하지 않음)
  python3 main.py check            등록부 검증 (네트워크 호출 없음)
  python3 main.py run [--source ID]  활성 소스 수집 및 저장 (네트워크 호출)
  python3 main.py summary          지수 등락률 요약 출력
  python3 main.py report           일일 시황 HTML 생성 (out/<기준일>/)
  python3 main.py feed [--port 8765]  뉴스 피드: 활성 뉴스 소스를 주기적으로 조회하고 127.0.0.1 페이지로 보여줌
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import registry  # noqa: E402
from core.config import env_file_exists, env_file_path, load_env  # noqa: E402
from core.logger import get_logger, mask  # noqa: E402
from core.storage import Store  # noqa: E402
from report import build, summary  # noqa: E402

DB = Path(os.environ["KBS_DB"]) if os.environ.get("KBS_DB") else ROOT / "data" / "data.db"
OUT = ROOT / "out"
log = get_logger()


def _print_sources(sources):
    print(f"키 파일: {env_file_path()}  (값은 표시하지 않음)")
    if not env_file_exists():
        print("경고: 키 파일이 없습니다. KBS_ENV_FILE 또는 기본 경로를 확인하세요.")
    print(f"{'id':12s} {'종류':11s} {'등록':9s} {'유효 상태':9s} 키")
    for s in sources:
        keys = " ".join(f"{k}{'✔' if ok else '✘'}" for k, ok in s.key_ok.items()) or "-"
        print(f"{s.id:12s} {s.kind:11s} {s.status:9s} {s.effective:9s} {keys}")


def cmd_sources(_args):
    sources, _found = registry.resolve()
    _print_sources(sources)
    return 0


def cmd_check(_args):
    sources, found = registry.resolve()
    _print_sources(sources)
    problems = registry.validate(sources, found, registry.load_kinds())
    print()
    if problems:
        print("검증 문제:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("검증 통과: 등록부 문제 없음")
    return 0


def cmd_run(args):
    sources, found = registry.resolve()
    kinds = registry.load_kinds()
    env = load_env()
    targets = [s for s in sources if s.effective == "활성" and (not args.source or s.id == args.source)]
    if not targets:
        print("실행할 활성 소스가 없습니다. (sources 명령으로 상태를 확인하세요)")
        return 0
    store = Store(DB)
    failed = 0
    try:
        for s in targets:
            adapter = found[s.adapter]
            try:
                raw = adapter.fetch(s.extra, env)
                store.save_raw(s.id, json.dumps(raw, ensure_ascii=False))
                items = adapter.normalize(raw, s.extra)
                bad = registry.check_items(kinds[s.kind], items)
                if bad:
                    raise ValueError(f"필수 필드 검사 실패 {len(bad)}건, 예: {bad[0]}")
                ins, upd = store.upsert_records(s.kind, s.id, items)
                store.set_status_ok(s.id)
                print(f"{s.id}: 신규 {ins}, 갱신 {upd}")
            except Exception as e:  # 소스 하나의 실패가 전체를 멈추지 않는다
                failed += 1
                msg = mask(f"{type(e).__name__}: {e}")
                store.set_status_error(s.id, msg)
                print(f"{s.id}: 실패 - {msg}")
    finally:
        store.close()
    return 1 if failed else 0


def cmd_summary(_args):
    store = Store(DB)
    try:
        rows = summary.index_changes(store)
    finally:
        store.close()
    if not rows:
        print("지수 데이터가 없습니다. 먼저 run을 실행하세요.")
        return 0
    print(f"{'지수':28s} {'종가':>12s} {'등락률':>9s}  관측일 (현재 / 전일)")
    for r in rows:
        print(f"{r['name']:28s} {r['value']:>12,.2f} {r['change_pct']:>+8.2f}%  {r['date']} / {r['prev_date']}")
    return 0


def cmd_report(_args):
    store = Store(DB)
    try:
        res = build.build_daily(store, OUT, tier=1)
    finally:
        store.close()
    print(f"기준일 {res['as_of']} · 지수 {res['index_rows']}개")
    print(f"HTML: {res['html']}")
    return 0


def cmd_feed(args):
    from server.feed import run_feed

    return run_feed(DB, port=args.port)


def cmd_all(args):
    """인자 없이 실행: 활성 소스 수집 → 지수 요약 → 보고서. 수집 실패가 있어도 요약과 보고서는 실행한다."""
    rc = cmd_run(argparse.Namespace(source=None))
    print()
    cmd_summary(args)
    print()
    cmd_report(args)
    return rc


def main(argv=None):
    p = argparse.ArgumentParser(description="Site-Conn-Github 수집·제공 프로토타입 (인자 없으면 수집·요약·보고서 일괄 실행)")
    sub = p.add_subparsers(dest="cmd", required=False)
    sub.add_parser("sources")
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("--source", default=None)
    sub.add_parser("summary")
    sub.add_parser("report")
    fd = sub.add_parser("feed")
    fd.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)
    if args.cmd is None:
        return cmd_all(args)
    return {"sources": cmd_sources, "check": cmd_check, "run": cmd_run,
            "summary": cmd_summary, "report": cmd_report, "feed": cmd_feed}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
