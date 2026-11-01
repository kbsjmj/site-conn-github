"""GitHub Actions 수집 진입점. 등록부(config/sources.json)의 활성 소스를 차례로 수집해 Supabase에 저장한다.

- --group all: 전부 실행 (수동 실행). daily: 하루 한 번 소스. news: 30분마다 도는 뉴스 소스.
- 소스 하나의 실패가 다른 소스를 멈추지 않는다 (실패 격리). 실패는 source_status에 남긴다.
- 실패가 하나라도 있으면 종료 코드 1로 끝나서 Actions 실행이 실패로 보인다.
- 키 값은 출력하지 않는다. 오류는 종류와 메시지만 남긴다.

실행: cd P2 && python -m collectors.run --group all
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import dart, fred, finnhub_news, naver_news, newsdata
from .store import SupabaseStore

CONFIG = Path(__file__).resolve().parent.parent / "config" / "sources.json"
ADAPTERS = {
    "fred": fred,
    "dart": dart,
    "newsdata": newsdata,
    "naver_news": naver_news,
    "finnhub_news": finnhub_news,
}


def dedupe(items):
    """같은 key가 두 번 들어오면 마지막 것만 남긴다 (한 번의 upsert에서 같은 행을 두 번 건드리면 실패하므로)."""
    seen = {}
    for it in items:
        seen[it["key"]] = it
    return list(seen.values())


def main(store=None, config_path=CONFIG, env=None, group="all"):
    env = os.environ if env is None else env
    sources = json.loads(Path(config_path).read_text(encoding="utf-8"))["sources"]
    store = store or SupabaseStore()

    failed = []
    for src in sources:
        sid = src["id"]
        if group != "all" and src.get("schedule", "daily") != group:
            continue
        if src.get("status") != "active":
            print(f"[건너뜀] {sid}: {src.get('status')}")
            continue
        mod = ADAPTERS.get(sid)
        try:
            if mod is None:
                raise RuntimeError("어댑터 없음")
            missing = [k for k in src.get("keys", []) if not env.get(k)]
            if missing:
                raise RuntimeError(f"키 없음: {', '.join(missing)}")
            raw = mod.fetch(src, env)
            raw_id = store.save_raw(sid, raw) if src.get("keep_raw", True) else None
            items = dedupe(mod.normalize(raw, src))
            n = store.upsert_records(mod.KIND, sid, items, raw_id)
            store.set_ok(sid)
            print(f"[성공] {sid}: {n}건 저장")
        except Exception as e:  # 소스별 격리: 어떤 실패도 다음 소스를 멈추지 않는다
            failed.append(sid)
            msg = f"{type(e).__name__}: {e}"
            try:
                store.set_error(sid, msg)
            except Exception:
                print(f"[경고] {sid}: 상태 기록도 실패")
            print(f"[실패] {sid}: {msg}")

    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", default="all", choices=["all", "daily", "news"])
    sys.exit(main(group=parser.parse_args().group))
