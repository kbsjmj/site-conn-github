"""등록부 로드, 어댑터 자동 탐색, 유효 상태 계산, 검증."""
import importlib
import pkgutil
from dataclasses import dataclass, field

import yaml

from .config import PROJECT, key_status

CONFIG = PROJECT / "config"
KNOWN = {"id", "adapter", "kind", "mode", "interval_min", "daily_limit", "keys", "realtime", "status", "license"}
REQUIRED = ("id", "adapter", "kind", "status")


@dataclass
class Source:
    id: str
    adapter: str
    kind: str
    mode: str
    interval_min: int
    daily_limit: object
    keys: list
    realtime: str
    status: str
    license: str
    extra: dict = field(default_factory=dict)
    effective: str = ""
    key_ok: dict = field(default_factory=dict)


def _yaml(name):
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8")) or {}


def load_kinds():
    return _yaml("kinds.yaml").get("kinds", {})


def load_report_cfg():
    return _yaml("report.yaml").get("report", {})


def load_sources():
    out = []
    for item in _yaml("sources.yaml").get("sources", []):
        missing = [k for k in REQUIRED if not item.get(k)]
        if missing:
            raise ValueError(f"sources.yaml 항목 필수 값 누락 {missing}: id={item.get('id')}")
        extra = {k: v for k, v in item.items() if k not in KNOWN}
        out.append(Source(
            id=item["id"], adapter=item["adapter"], kind=item["kind"],
            mode=item.get("mode", "poll"), interval_min=item.get("interval_min", 60),
            daily_limit=item.get("daily_limit"), keys=item.get("keys") or [],
            realtime=item.get("realtime", "daily"), status=item["status"],
            license=item.get("license", "확인 필요"), extra=extra,
        ))
    return out


def discover_adapters():
    import adapters

    found = {}
    for m in pkgutil.iter_modules(adapters.__path__):
        if m.name == "base":
            continue
        mod = importlib.import_module(f"adapters.{m.name}")
        cls = getattr(mod, "ADAPTER", None)
        if cls is not None:
            found[m.name] = cls
    return found


def resolve(sources=None):
    sources = sources if sources is not None else load_sources()
    found = discover_adapters()
    for s in sources:
        s.key_ok = key_status(s.keys)
        if s.status == "retired":
            s.effective = "퇴역"
        elif s.status == "paused":
            s.effective = "일시중지"
        elif s.adapter not in found:
            s.effective = "미구현"
        elif not all(s.key_ok.values()):
            s.effective = "키 없음"
        else:
            s.effective = "활성"
    return sources, found


def validate(sources, found, kinds):
    problems, seen = [], set()
    for s in sources:
        if s.id in seen:
            problems.append(f"{s.id}: id 중복")
        seen.add(s.id)
        if s.kind not in kinds:
            problems.append(f"{s.id}: kinds.yaml에 없는 종류 '{s.kind}'")
        if s.status not in ("active", "paused", "retired"):
            problems.append(f"{s.id}: 알 수 없는 status '{s.status}'")
        if s.status == "active" and s.adapter not in found:
            problems.append(f"{s.id}: active인데 어댑터 '{s.adapter}' 없음")
        if s.adapter in found and found[s.adapter].kind != s.kind:
            problems.append(f"{s.id}: 어댑터 종류 '{found[s.adapter].kind}' ≠ 등록 종류 '{s.kind}'")
    return problems


def check_items(kind_def, items):
    """정규화 결과가 kinds.yaml의 필수 필드를 갖췄는지 확인. 문제 목록을 반환."""
    required = kind_def.get("required", [])
    bad = []
    for it in items:
        missing = [f for f in required if it["payload"].get(f) in (None, "")]
        if missing:
            bad.append(f"{it.get('key')}: 누락 {missing}")
    return bad
