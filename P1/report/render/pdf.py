"""HTML → PDF. Mac에 설치된 Google Chrome을 헤드리스로 실행해 인쇄한다 (지침 9절 방식, 2026-11-04 구현).

- 머리글·바닥글(날짜, 주소, 쪽 번호)은 끈다 (--no-pdf-header-footer). v6.pdf에는 없었다.
- 실패하면 예외를 던진다. 조용히 넘어가지 않는다.
"""
import shutil
import subprocess
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def _chrome():
    for p in CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise FileNotFoundError("Chrome을 찾지 못했습니다. Google Chrome 설치를 확인하세요.")


def html_to_pdf(html_path, pdf_path, timeout=120):
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    if pdf_path.exists():
        raise FileExistsError(f"이미 있는 파일입니다 (덮어쓰지 않음): {pdf_path}")
    cmd = [
        _chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"PDF 변환 실패 (코드 {res.returncode}): {res.stderr.strip()[:300]}")
    return str(pdf_path)


def page_texts(pdf_path):
    """쪽별 텍스트 목록 (pdftotext 사용). pdftotext가 없으면 None."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    info = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True)
    pages = 0
    for line in info.stdout.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split()[1])
    out = []
    for i in range(1, pages + 1):
        r = subprocess.run([exe, "-f", str(i), "-l", str(i), str(pdf_path), "-"],
                           capture_output=True, text=True)
        out.append(r.stdout)
    return out
