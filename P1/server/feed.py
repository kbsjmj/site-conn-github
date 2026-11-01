"""뉴스 피드: 활성 news 소스를 주기적으로 조회해 저장하고, 127.0.0.1 페이지로 보여준다.

- 소스마다 poll_sec 주기로 조회한다 (sources.yaml). 스케줄러는 1초마다 깨어나 due 소스만 조회한다.
- 페이지는 /api/news를 10초마다 불러 새 기사만 위에 붙인다.
- 원본 응답(raw)은 keep_raw가 true인 소스만 저장한다. 기본은 저장하지 않는다 (10초 주기 누적을 막기 위해).
- 어떤 소스의 실패도 다른 소스와 서버를 멈추지 않는다.
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core import registry
from core.config import env_file_path, load_env
from core.logger import mask
from core.storage import Store

PAGE = Path(__file__).resolve().parent / "feed.html"
KST = timezone(timedelta(hours=9))
DEFAULT_PORT = 8765
TICK_SEC = 1.0
FIRST_PAGE = 50
MAX_BATCH = 100


def news_targets(sources):
    return [s for s in sources if s.kind == "news" and s.effective == "활성"]


def poll_sec(s):
    return int(s.extra.get("poll_sec", max(1, int(s.interval_min or 1)) * 60))


def quota_lines(targets):
    lines = []
    for s in targets:
        per_day = 86400 // poll_sec(s)
        limit = f"일 한도 {s.daily_limit}" if s.daily_limit else "공식 한도 미확인"
        lines.append(f"{s.id}: {poll_sec(s)}초마다 (하루 최대 {per_day}회, {limit})")
    return lines


def poll_once(store, s, env, found, kinds, tick):
    """소스 하나를 한 번 조회해 저장한다. 반환: (새 기사 수, 오류 메시지 또는 None)."""
    cfg = {**s.extra, "_tick": tick}
    adapter = found[s.adapter]
    try:
        raw = adapter.fetch(cfg, env)
        if s.extra.get("keep_raw"):
            store.save_raw(s.id, json.dumps(raw, ensure_ascii=False))
        items = adapter.normalize(raw, cfg)
        bad = registry.check_items(kinds[s.kind], items)
        if bad:
            raise ValueError(f"필수 필드 검사 실패 {len(bad)}건, 예: {bad[0]}")
        inserted, _updated = store.upsert_records(s.kind, s.id, items)
        store.set_status_ok(s.id)
        return inserted, None
    except Exception as e:  # 소스 하나의 실패가 나머지를 멈추지 않는다
        msg = mask(f"{type(e).__name__}: {e}")
        store.set_status_error(s.id, msg)
        return 0, msg


class Poller(threading.Thread):
    def __init__(self, db_path, targets, found, kinds, env):
        super().__init__(daemon=True, name="news-poller")
        self.db_path = db_path
        self.targets = targets
        self.found = found
        self.kinds = kinds
        self.env = env
        self.stop_event = threading.Event()

    def run(self):
        store = Store(self.db_path)  # 스레드마다 자기 연결을 쓴다
        next_due = {s.id: 0.0 for s in self.targets}
        ticks = {s.id: 0 for s in self.targets}
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                for s in self.targets:
                    if now < next_due[s.id]:
                        continue
                    next_due[s.id] = now + poll_sec(s)
                    ticks[s.id] += 1
                    inserted, err = poll_once(store, s, self.env, self.found, self.kinds, ticks[s.id])
                    stamp = datetime.now(KST).strftime("%H:%M:%S")
                    print(f"[{stamp}] {s.id}: " + (f"실패 - {err}" if err else f"새 기사 {inserted}건"), flush=True)
                self.stop_event.wait(TICK_SEC)
        finally:
            store.close()


def news_payload(store, news_ids, after=None):
    """after가 없으면 최신 FIRST_PAGE건(오래된 순), 있으면 그 seq 이후 새 기사(오래된 순)."""
    if after is None:
        rows = list(reversed(store.recent("news", FIRST_PAGE)))
    else:
        rows = store.after("news", after, MAX_BATCH)
    items = []
    for r in rows:
        p = r["payload"]
        items.append({
            "seq": r["seq"],
            "feed": r["source"],
            "region": p.get("region", ""),
            "source": p.get("source") or "",
            "title": p.get("title", ""),
            "url": p.get("url", ""),
            "published_at": p.get("published_at", ""),
            "summary": (p.get("summary") or "")[:300],
            "query": p.get("query", ""),
        })
    last_seq = max((i["seq"] for i in items), default=after or 0)
    status = [st for st in store.statuses() if st["source"] in news_ids]
    return {
        "items": items,
        "last_seq": last_seq,
        "status": status,
        "now": datetime.now(KST).isoformat(timespec="seconds"),
    }


def make_handler(db_path, news_ids):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # 요청마다 로그를 남기지 않는다
            return

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._send(200, "text/html; charset=utf-8", PAGE.read_bytes())
            if u.path == "/api/news":
                raw_after = parse_qs(u.query).get("after", [""])[0]
                try:
                    after = int(raw_after) if raw_after else None
                except ValueError:
                    return self._send(400, "application/json; charset=utf-8",
                                      b'{"error":"after\xec\x9d\x80 \xec\xa0\x95\xec\x88\x98\xec\x97\xac\xec\x95\xbc \xed\x95\xa9\xeb\x8b\x88\xeb\x8b\xa4"}')
                store = Store(db_path)
                try:
                    data = news_payload(store, news_ids, after)
                finally:
                    store.close()
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                return self._send(200, "application/json; charset=utf-8", body)
            return self._send(404, "text/plain; charset=utf-8", b"not found")

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_feed(db_path, port=DEFAULT_PORT):
    sources, found = registry.resolve()
    kinds = registry.load_kinds()
    env = load_env()
    targets = news_targets(sources)
    if not targets:
        print("활성 뉴스 소스가 없습니다. `python3 main.py run --source <id>`로 확인한 뒤 "
              "sources.yaml의 status를 active로 바꾸세요.")
        return 0
    print(f"키 파일: {env_file_path()}  (값은 표시하지 않음)")
    print("조회 주기:")
    for line in quota_lines(targets):
        print(f"  {line}")
    news_ids = {s.id for s in targets}
    poller = Poller(db_path, targets, found, kinds, env)
    poller.start()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db_path, news_ids))
    print(f"페이지: http://127.0.0.1:{port}/  (Ctrl+C로 종료)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        poller.stop_event.set()
        httpd.server_close()
    return 0
