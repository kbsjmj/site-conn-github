"""등록부 검사. 등록부, 어댑터, 워크플로가 서로 어긋나면 테스트가 실패한다."""
import json
import unittest
from pathlib import Path

from collectors import run

P2 = Path(__file__).resolve().parents[1]
CONFIG = P2 / "config" / "sources.json"
WORKFLOW = P2.parent / ".github" / "workflows" / "collect.yml"
STATUSES = {"active", "paused", "retired"}


def load():
    return json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]


class RegistryTests(unittest.TestCase):
    def test_ids_are_unique_and_statuses_are_valid(self):
        ids = [s["id"] for s in load()]
        self.assertEqual(len(ids), len(set(ids)))
        for s in load():
            self.assertIn(s["status"], STATUSES, s["id"])

    def test_every_entry_says_why_or_has_a_license(self):
        for s in load():
            self.assertTrue(s.get("note") or s.get("license"), s["id"])

    def test_every_active_source_has_an_adapter(self):
        for s in load():
            if s["status"] == "active":
                self.assertIn(s["id"], run.ADAPTERS, s["id"])

    def test_every_active_key_is_passed_by_the_workflow(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for s in load():
            if s["status"] != "active":
                continue
            for key in s.get("keys", []):
                self.assertIn(f"{key}: ${{{{ secrets.{key} }}}}", workflow, f"{s['id']} -> {key}")


if __name__ == "__main__":
    unittest.main()
