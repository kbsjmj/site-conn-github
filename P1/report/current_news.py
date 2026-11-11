"""현재시황뉴스 보고서 생성: 입력 JSON → 표 검산 → HTML(v6 양식) → PDF → 기록(manifest).

- 입력 파일: P1/report/inputs/현재시황뉴스 (YYYYMMDD)-vN.json
  문장(요인 판단, 해설, 교차 확인 기록)은 사람(Claude)이 쓰고, 이 프로그램은 숫자 검산과 배치만 한다.
- 산출물: 프로젝트 폴더 루트에 현재시황뉴스 (YYYYMMDD)-vN.html 과 .pdf (지침 8-1).
- 기존 파일은 절대 덮어쓰지 않는다. 같은 번호가 있으면 실패한다.
- 같은 입력 파일(해시 기준)은 두 번 만들지 않는다 (기본 실행의 report 단계).
"""
import hashlib
import html
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from core.config import PROJECT

from . import numbers
from .render import pdf as pdf_render

INPUT_DIR = PROJECT / "report" / "inputs"
TEMPLATE = PROJECT / "report" / "templates" / "current_news.html"
MANIFEST_DIR = PROJECT / "out"
OUT_ROOT = PROJECT.parent  # 프로젝트 폴더 루트 (지침 8-1)

NAME_RE = re.compile(r"^현재시황뉴스 \((\d{8})\)-v(\d+)\.(html|pdf)$")
TIER_LABEL = {1: "개인 전용"}
BLOCK_TYPES = {"h2", "h3", "p", "src", "box", "note", "table"}
PAGES = 4  # 지침 9절 12번: 전체 4쪽 이하


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(doc):
    """입력 형식과 숫자 검산. 문제 목록을 돌려준다 (비어 있으면 통과)."""
    problems = []
    date = str(doc.get("report_date", ""))
    if not re.fullmatch(r"\d{8}", date):
        problems.append("report_date는 YYYYMMDD 여덟 자리여야 합니다")
    for key in ("written_at", "news_basis", "price_basis"):
        if not str(doc.get(key, "")).strip():
            problems.append(f"{key} 값이 비어 있습니다")
    if doc.get("tier") != 1:
        problems.append("재배포 등급은 1만 지원합니다 (지침 6절)")
    if not doc.get("sections"):
        problems.append("sections가 비어 있습니다")
    if not doc.get("sources"):
        problems.append("sources(출처 목록)가 비어 있습니다")
    for i, b in enumerate(doc.get("sections", [])):
        if b.get("type") not in BLOCK_TYPES:
            problems.append(f"sections[{i}]: 알 수 없는 종류 {b.get('type')!r}")
        if b.get("type") == "table":
            for row in b.get("rows", []):
                if len(row.get("cells", [])) != len(b.get("columns", [])):
                    problems.append(f"표 행의 칸 수가 머리글과 다릅니다: {row.get('cells')}")
            problems.extend(numbers.check_table(b.get("rows", [])))
    return problems


def _inline(text):
    """이스케이프 후 **굵게** 표시만 바꾼다."""
    s = html.escape(str(text), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def _sign_class(text, col_index):
    """표의 숫자 칸: 앞이 +면 빨강(.up), -면 파랑(.dn). 첫 칸(이름)과 기호 없는 값은 그대로 둔다 (지침 9절 8번)."""
    if col_index == 0:
        return ""
    m = re.match(r"^\s*([+-])", str(text))
    if not m:
        return ""
    return "up" if m.group(1) == "+" else "dn"


def _render_table(block):
    cols = block["columns"]
    n = len(cols)
    colgroup = '<colgroup><col class="c-name">' + '<col class="c-num">' * (n - 1) + "</colgroup>"
    head = "".join(f"<th>{_inline(c)}</th>" for c in cols)
    rows = []
    for row in block["rows"]:
        tds = []
        for i, cell in enumerate(row["cells"]):
            inner = html.escape(str(cell), quote=False)
            cls = _sign_class(cell, i)
            if cls:
                inner = f'<span class="{cls}">{inner}</span>'
            tds.append(f"<td>{inner}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (f"<table>\n  {colgroup}\n  <thead>\n    <tr>{head}</tr>\n  </thead>\n"
            f"  <tbody>\n" + "\n".join(rows) + "\n  </tbody>\n</table>")


def _render_block(b):
    t = b["type"]
    if t == "h2":
        style = ' style="page-break-before: always;"' if b.get("page_break") else ""
        return f"<h2{style}>{_inline(b['text'])}</h2>"
    if t == "h3":
        return f"<h3>{_inline(b['text'])}</h3>"
    if t == "p":
        cls = ' class="lead"' if b.get("style") == "lead" else ""
        parts = []
        if b.get("tag"):
            parts.append(f'<span class="tag {html.escape(b["tag"])}">{_inline(b.get("label", ""))}</span>')
        if b.get("bold"):
            parts.append(f"<strong>{_inline(b['bold'])}</strong>")
        parts.append(_inline(b.get("text", "")))
        return f"<p{cls}>" + " ".join(p for p in parts if p) + "</p>"
    if t == "src":
        prefix = f"<strong>{_inline(b['bold'])}</strong> " if b.get("bold") else ""
        return f'<div class="src">{prefix}{_inline(b.get("text", ""))}</div>'
    if t == "box":
        return '<div class="scope">' + "<br>\n  ".join(_inline(x) for x in b["lines"]) + "</div>"
    if t == "note":
        return '<div class="note">' + "<br>".join(_inline(x) for x in b["lines"]) + "</div>"
    if t == "table":
        return _render_table(b)
    raise ValueError(f"알 수 없는 블록: {t}")


def render_html(doc, report_no):
    date = doc["report_date"]
    title = f"현재시황뉴스 ({date})"
    meta = (f"작성 {doc['written_at']} · 뉴스 기준: {doc['news_basis']} · "
            f"시세 기준: {doc['price_basis']} · 보고서 v{report_no} · "
            f"재배포 등급 {doc['tier']} ({TIER_LABEL[doc['tier']]})")
    body = "\n".join(_render_block(b) for b in doc["sections"])
    src_items = "\n".join(f"    <li>{_inline(s)}</li>" for s in doc["sources"])
    footer = (f"\n<footer>\n  <strong>{_inline(doc.get('sources_title', '출처'))}</strong>\n"
              f"  <ol class=\"src-list\">\n{src_items}\n  </ol>\n"
              f"  <p>{_inline(doc.get('footer_note', ''))}</p>\n</footer>")
    template = TEMPLATE.read_text(encoding="utf-8")
    out = (template.replace("{{TITLE}}", html.escape(title))
                   .replace("{{META}}", _inline(meta))
                   .replace("{{BODY}}", body + footer))
    return out


def next_report_no(out_root, date):
    nums = []
    for p in Path(out_root).iterdir():
        m = NAME_RE.match(p.name)
        if m and m.group(1) == date:
            nums.append(int(m.group(2)))
    return max(nums, default=0) + 1


def layout_problems(pages):
    """지침 9절 6번 쪽 확인. pages는 쪽별 텍스트 목록 (None이면 확인 생략)."""
    if pages is None:
        return ["pdftotext가 없어 쪽 배치를 확인하지 못했습니다"]
    problems = []
    if len(pages) > PAGES:
        problems.append(f"쪽 수 {len(pages)}쪽 (기준 {PAGES}쪽 이하)")

    def first_line(text):
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return ""

    if len(pages) >= 2 and not first_line(pages[1]).startswith("2. 주요 경제 지표"):
        problems.append("2쪽 첫 줄이 '2. 주요 경제 지표'가 아닙니다")
    if len(pages) >= 3 and not first_line(pages[2]).startswith("3. 참고 사항"):
        problems.append("3쪽 첫 줄이 '3. 참고 사항'이 아닙니다")
    if pages and ("1-3." not in pages[0] or "2. 주요 경제 지표" in pages[0]):
        problems.append("단락 1(1-1~1-3)이 1쪽 안에 들어가지 않습니다")
    return problems


def build(input_path, out_root=OUT_ROOT, pdf=True, manifest_dir=MANIFEST_DIR):
    input_path = Path(input_path)
    sha = sha256_of(input_path)
    doc = json.loads(input_path.read_text(encoding="utf-8"))
    problems = validate(doc)
    if problems:
        raise ValueError("입력 검산 실패 (보고서를 만들지 않음):\n  - " + "\n  - ".join(problems))

    date = doc["report_date"]
    n = doc.get("report_no") or next_report_no(out_root, date)
    stem = f"현재시황뉴스 ({date})-v{n}"
    html_path = Path(out_root) / f"{stem}.html"
    pdf_path = Path(out_root) / f"{stem}.pdf"
    for p in (html_path, pdf_path):
        if p.exists():
            raise FileExistsError(f"이미 있는 파일입니다 (덮어쓰지 않음): {p}")

    rendered = render_html(doc, n)
    result = {"stem": stem, "html": None, "pdf": None, "layout": []}
    if pdf:
        # 2026-11-08 메모: 보고서는 PDF만 남긴다. HTML은 PDF 변환용 임시 파일로만 쓰고 바로 지운다.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_html = Path(tmp) / f"{stem}.html"
            tmp_html.write_text(rendered, encoding="utf-8")
            pdf_render.html_to_pdf(tmp_html, pdf_path)
        result["pdf"] = str(pdf_path)
        result["layout"] = layout_problems(pdf_render.page_texts(pdf_path))
    else:
        html_path.write_text(rendered, encoding="utf-8")
        result["html"] = str(html_path)

    record = {
        "report": "현재시황뉴스",
        "report_date": date,
        "report_no": n,
        "input_file": input_path.name,
        "input_sha256": sha,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "outputs": {"html": None if pdf else html_path.name, "pdf": pdf_path.name if pdf else None},
        "table_check": "통과",
        "layout_problems": result["layout"],
    }
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / f"{stem}.manifest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def built_hashes(manifest_dir=MANIFEST_DIR):
    seen = set()
    for p in Path(manifest_dir).glob("*.manifest.json"):
        try:
            seen.add(json.loads(p.read_text(encoding="utf-8")).get("input_sha256"))
        except (OSError, ValueError):
            continue
    return seen


def build_pending(out_root=OUT_ROOT, pdf=True):
    """입력 폴더에서 아직 만들지 않은 입력 파일만 만든다. 없으면 빈 목록."""
    done = built_hashes()
    results = []
    for p in sorted(INPUT_DIR.glob("*.json")):
        if sha256_of(p) in done:
            continue
        results.append(build(p, out_root=out_root, pdf=pdf))
    return results
