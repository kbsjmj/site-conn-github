"""키 로더. 값은 메모리에만 두고, 출력은 이름과 존재 여부만 한다.

우선순위: 환경변수 KBS_ENV_FILE > ~/.config/restconn/.env > /Users/KBS/kbsjmj/.env
"""
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SHARED_ENV = Path.home() / ".config" / "restconn" / ".env"
# 키 파일 기본 위치: 사용자 폴더 루트 (P1 바깥). 2026-10-31 이동.
DEFAULT_ENV = Path("/Users/KBS/kbsjmj/.env")


def env_file_path() -> Path:
    override = os.environ.get("KBS_ENV_FILE")
    if override:
        return Path(override)
    if SHARED_ENV.exists():
        return SHARED_ENV
    return DEFAULT_ENV


def env_file_exists() -> bool:
    return env_file_path().exists()


def parse_env(path) -> dict:
    values = {}
    p = Path(path)
    if not p.exists():
        return values
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k or not v:
            continue  # 빈 값은 무시한다 (빈 줄 때문에 값이 덮이는 문제 방지)
        values.setdefault(k, v)  # 처음 나온 비어 있지 않은 값을 쓴다
    return values


_cache = None


def load_env() -> dict:
    global _cache
    if _cache is None:
        _cache = parse_env(env_file_path())
    return _cache


def key_status(names) -> dict:
    env = load_env()
    return {n: bool(env.get(n)) for n in names}
