"""어댑터 공통 인터페이스.

- fetch(cfg, env): 원본 응답(JSON 가능한 객체)을 반환한다. 키는 env에서 읽는다.
- normalize(raw, cfg): [{key, observed_at, payload}] 목록을 반환한다. payload는 kinds.yaml 필수 필드를 채운다.
- 모듈 끝에 ADAPTER = 인스턴스 를 둔다. 레지스트리가 이를 찾아 등록한다.
"""
from abc import ABC, abstractmethod


class Adapter(ABC):
    name = ""
    kind = ""
    required_keys = ()

    @abstractmethod
    def fetch(self, cfg, env):
        ...

    @abstractmethod
    def normalize(self, raw, cfg):
        ...
