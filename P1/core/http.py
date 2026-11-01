"""HTTP 호출. certifi 인증서 번들을 쓰고 SSL 검증은 끄지 않는다. 실패 메시지에는 URL과 키를 넣지 않는다."""
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # certifi가 없으면 시스템 기본 번들
    _CTX = ssl.create_default_context()


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def get_json(url, params=None, headers=None, timeout=15, retries=2, backoff=2.0):
    full = url
    if params:
        full = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers=headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, context=_CTX, timeout=timeout) as r:
                body = r.read().decode("utf-8")
            try:
                return json.loads(body)
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
