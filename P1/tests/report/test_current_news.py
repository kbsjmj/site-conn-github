import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from report import current_news as cn  # noqa: E402
from report import numbers  # noqa: E402

# 입력 JSON은 프로젝트에 두지 않는다 (검증 때만 임시 폴더에서 사용). 없으면 그 테스트는 건너뛴다.
INPUT = cn.INPUT_DIR / "현재시황뉴스 (20261109)-v2.json"
HAS_INPUT = INPUT.exists()
needs_input = unittest.skipUnless(HAS_INPUT, "검증 입력 JSON이 report/inputs에 없음")


class NumbersTest(unittest.TestCase):
    @needs_input
    def test_input_numbers_pass(self):
        doc = json.loads(INPUT.read_text(encoding="utf-8"))
        self.assertEqual([], cn.validate(doc))

    def test_wrong_percent_is_detected(self):
        cells = ["코스피", "5,715.23", "-143.85", "-2.40%"]
        chk = {"close": 5715.23, "change": -143.85, "pct": -2.40}
        problems = numbers.check_row("코스피", cells, chk)
        self.assertTrue(any("등락률 계산" in p for p in problems), problems)

    def test_text_not_matching_input_is_detected(self):
        cells = ["코스닥", "718.5", "-15.82", "-2.15%"]
        chk = {"close": 718.54, "change": -15.82, "pct": -2.15}
        problems = numbers.check_row("코스닥", cells, chk)
        self.assertTrue(any("종가 표 글자" in p for p in problems), problems)

    def test_range_and_dash_are_not_checked(self):
        self.assertIsNone(numbers.parse_cell("4.896~4.91%"))
        self.assertIsNone(numbers.parse_cell("—"))
        self.assertEqual(1342.3, numbers.parse_cell("1,342.3원"))


class RenderTest(unittest.TestCase):
    def test_sign_classes(self):
        self.assertEqual("up", cn._sign_class("+1.86", 1))
        self.assertEqual("dn", cn._sign_class("-2~-4bp", 2))
        self.assertEqual("", cn._sign_class("4.896~4.91%", 1))
        self.assertEqual("", cn._sign_class("+9.58%", 0))  # 이름 칸은 색을 입히지 않는다

    def test_inline_escapes_and_bolds(self):
        self.assertEqual("S&amp;P &lt;x&gt; <strong>b</strong>", cn._inline("S&P <x> **b**"))

    @needs_input
    def test_html_contains_v6_structure(self):
        doc = json.loads(INPUT.read_text(encoding="utf-8"))
        out = cn.render_html(doc, doc.get("report_no") or 2)
        self.assertIn("<title>현재시황뉴스 (20261109)</title>", out)
        self.assertIn('class="tag up"', out)
        self.assertIn('class="tag down"', out)
        self.assertIn('style="page-break-before: always;"', out)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    @needs_input
    def test_build_writes_html_and_refuses_overwrite(self):
        res = cn.build(INPUT, out_root=self.root, pdf=False, manifest_dir=self.root / "m")
        self.assertTrue(Path(res["html"]).exists())
        self.assertTrue((self.root / "m" / "현재시황뉴스 (20261109)-v2.manifest.json").exists())
        with self.assertRaises(FileExistsError):
            cn.build(INPUT, out_root=self.root, pdf=False, manifest_dir=self.root / "m")

    @needs_input
    def test_bad_input_writes_nothing(self):
        doc = json.loads(INPUT.read_text(encoding="utf-8"))
        doc["report_no"] = 99
        # 검산 대상 행의 등락률 글자를 틀리게 바꾼다
        row = next(r for b in doc["sections"] if b["type"] == "table"
                   for r in b["rows"] if "check" in r)
        row["cells"][3] = "+9.99%"
        src_dir = Path(tempfile.mkdtemp())
        bad = src_dir / "bad.json"
        bad.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        out = self.root / "out"
        out.mkdir()
        with self.assertRaises(ValueError):
            cn.build(bad, out_root=out, pdf=False, manifest_dir=self.root / "m")
        self.assertEqual([], list(out.iterdir()))

    def test_next_report_no(self):
        self.assertEqual(1, cn.next_report_no(self.root, "20261109"))
        (self.root / "현재시황뉴스 (20261109)-v6.html").write_text("x", encoding="utf-8")
        (self.root / "현재시황뉴스 (20261108)-v30.pdf").write_text("x", encoding="utf-8")
        self.assertEqual(7, cn.next_report_no(self.root, "20261109"))

    def test_layout_problems(self):
        ok = ["1. 증시 추세 요약 1-3. 수급", "2. 주요 경제 지표 2-1.", "3. 참고 사항 뉴스"]
        self.assertEqual([], cn.layout_problems(ok))
        bad = ["1. 증시 추세 요약 1-3.", "2-1. 표", "3. 참고 사항"]
        self.assertTrue(cn.layout_problems(bad))
        self.assertTrue(cn.layout_problems(ok + ["extra", "more"]))  # 5쪽 이상은 실패

    @needs_input
    def test_validate_rejects_bad_fields(self):
        doc = json.loads(INPUT.read_text(encoding="utf-8"))
        d = copy.deepcopy(doc)
        d["tier"] = 2
        d["report_date"] = "2026-11-09"
        problems = cn.validate(d)
        self.assertTrue(any("등급" in p for p in problems))
        self.assertTrue(any("report_date" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
