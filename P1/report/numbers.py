"""표 숫자 검산 (지침 3: 계산은 코드로 한다).

표의 한 행에 종가, 등락, 등락률이 모두 있으면 다음을 확인한다.
- 표에 적힌 글자가 입력 값과 같은가 (오타 방지)
- 전일 종가 = 종가 - 등락 으로 역산하고, 등락 / 전일 종가 × 100 이 표의 등락률과 소수 둘째 자리까지 같은가

범위 값(예: 4.896~4.91%)과 '—'는 검산하지 않는다.
"""


def parse_cell(text):
    """'+1.86', '1,342.3원', '-7.36%' 같은 글자를 숫자로 바꾼다. 범위나 '—'는 None."""
    s = str(text).strip().replace(",", "").replace("원", "").replace("%", "")
    if s in ("", "—", "-", "+") or "~" in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def check_row(label, cells, check):
    """cells: [이름, 종가글자, 등락글자, 등락률글자]. check: {'close', 'change', 'pct'} 숫자.
    반환: 문제 설명 목록 (비어 있으면 통과)."""
    problems = []
    close_txt, chg_txt, pct_txt = cells[1], cells[2], cells[3]
    if parse_cell(close_txt) != check["close"]:
        problems.append(f"{label}: 종가 표 글자 {close_txt!r} ≠ 입력 {check['close']}")
    if parse_cell(chg_txt) != check["change"]:
        problems.append(f"{label}: 등락 표 글자 {chg_txt!r} ≠ 입력 {check['change']}")
    if parse_cell(pct_txt) != check["pct"]:
        problems.append(f"{label}: 등락률 표 글자 {pct_txt!r} ≠ 입력 {check['pct']}")

    prev = check["close"] - check["change"]
    if prev == 0:
        problems.append(f"{label}: 전일 종가가 0이라 등락률을 계산할 수 없다")
        return problems
    calc = round(check["change"] / prev * 100, 2)
    if abs(calc - check["pct"]) > 1e-9:
        problems.append(
            f"{label}: 등락률 계산 {calc:+.2f}% ≠ 표 {check['pct']:+.2f}% "
            f"(전일 종가 역산 {prev:,.2f})"
        )
    return problems


def check_table(rows):
    """표 한 개의 모든 행을 검산한다. 행 객체: {'cells': [...], 'check': {...}(선택)}."""
    problems = []
    for row in rows:
        chk = row.get("check")
        if chk is None:
            continue
        problems.extend(check_row(row["cells"][0], row["cells"], chk))
    return problems
