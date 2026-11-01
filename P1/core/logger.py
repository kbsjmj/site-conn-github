import logging
import re

_PAT = re.compile(r"((?:api[_-]?key|crtfc_key|serviceKey|apikey|token|secret|appkey|secretkey|api_key)=)[^&\s'\"]+", re.I)


def mask(text) -> str:
    return _PAT.sub(r"\1***", str(text))


class _MaskFilter(logging.Filter):
    def filter(self, record):
        record.msg = mask(record.getMessage())
        record.args = ()
        return True


def get_logger(name="restconn") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        h.addFilter(_MaskFilter())
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log
