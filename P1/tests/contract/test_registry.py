import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import registry  # noqa: E402


class RegistryTest(unittest.TestCase):
    def test_sources_load_and_validate_clean(self):
        sources, found = registry.resolve()
        kinds = registry.load_kinds()
        self.assertTrue(sources)
        self.assertEqual([], registry.validate(sources, found, kinds))

    def test_paused_sources_show_paused(self):
        sources, _ = registry.resolve()
        for s in sources:
            if s.status == "paused":
                self.assertEqual("일시중지", s.effective)

    def test_every_effective_state_is_known(self):
        sources, _ = registry.resolve()
        allowed = {"활성", "일시중지", "퇴역", "미구현", "키 없음"}
        for s in sources:
            self.assertIn(s.effective, allowed)

    def test_unknown_kind_is_reported(self):
        s = registry.Source(id="x", adapter="fred", kind="nope", mode="poll", interval_min=1,
                            daily_limit=None, keys=[], realtime="daily", status="active", license="")
        problems = registry.validate([s], {"fred": registry.discover_adapters()["fred"]}, registry.load_kinds())
        self.assertTrue(any("nope" in p for p in problems))

    def test_active_without_adapter_is_reported(self):
        s = registry.Source(id="y", adapter="ghost", kind="index", mode="poll", interval_min=1,
                            daily_limit=None, keys=[], realtime="daily", status="active", license="")
        problems = registry.validate([s], {}, registry.load_kinds())
        self.assertTrue(any("ghost" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
