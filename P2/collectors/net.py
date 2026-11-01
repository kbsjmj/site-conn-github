"""HTTP 호출 (표준 라이브러리 + certifi). SSL 검증은 끄지 않는다.
오류 메시지에는 URL과 키를 넣지 않는다 (상태 코드와 종류만 남긴다)."""
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # certifi가 없으면 시스템 기본 인증서
    _CTX = ssl.create_default_context()


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def request_json(method, url, params=None, headers=None, body=None,
                 timeout=20, retries=2, backoff=2.0):
    full = url
    if params:
        full = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    hdrs = dict(headers or {})
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(full, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, context=_CTX, timeout=timeout) as r:
                text = r.read().decode("utf-8")
            if not text:
                return None
            try:
                return json.loads(text)
            except ValueError:
                raise HttpError(200, "응답 형식 오류 (JSON 아님)")
        except urllib.error.HTTPError as e:
            last = HttpError(e.code, f"HTTP {e.code}")
            if e.code in (400, 401, 403, 404):
                break  # 재시도해도 소용없음
        except HttpError as e:
            last = e
            break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = HttpError(0, f"네트워크 오류: {type(e).__name__}")
        if attempt < retries:
            time.sleep(backoff ** attempt)
    raise last


def get_json(url, params=None, headers=None, **kw):
    return request_json("GET", url, params=params, headers=headers, **kw)
