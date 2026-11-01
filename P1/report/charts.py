"""등락률 차트 (dataviz 스킬 기준).

- 형식: 발산형 가로 막대. 역할이 '부호(상승/하락)'이므로 발산형을 쓴다.
- 색: 파랑(상승) ↔ 빨강(하락), 중간선은 회색 축선. 색 값은 CSS 변수로 두어 라이트/다크를 한곳에서 바꾼다.
- 식별은 색만으로 하지 않는다: 값 라벨에 부호(+, -)를 함께 쓴다.
- 직접 라벨: 막대마다 이름과 값을 붙인다. 표 보기는 HTML 본문 표가 맡는다.
- 호버: 막대마다 <title>로 상세 툴팁을 준다.
"""
from html import escape


def _bar_path(x0, x1, y, h, r, round_side):
    r = max(0.0, min(r, (x1 - x0) / 2, h / 2))
    if round_side == "right":
        return (f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
                f"V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z")
    return (f"M{x1:.1f},{y:.1f} H{x0 + r:.1f} Q{x0:.1f},{y:.1f} {x0:.1f},{y + r:.1f} "
            f"V{y + h - r:.1f} Q{x0:.1f},{y + h:.1f} {x0 + r:.1f},{y + h:.1f} H{x1:.1f} Z")


def change_bar_svg(rows):
    if not rows:
        return ""
    W, x0, x1 = 400, 20, 380
    mid = (x0 + x1) / 2
    half = (x1 - x0) / 2 * 0.75
    row_h, bar_h, pad_top = 56, 22, 16
    H = pad_top + len(rows) * row_h + 8
    max_abs = max(max(abs(r["change_pct"]) for r in rows), 0.01)

    desc = "; ".join(f"{r['name']} {r['change_pct']:+.2f}%" for r in rows)
    parts = [
        f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="chart-title chart-desc">',
        '<title id="chart-title">지수 전일 대비 등락률</title>',
        f'<desc id="chart-desc">{escape(desc)}</desc>',
    ]
    for i, r in enumerate(rows):
        top = pad_top + i * row_h
        bar_y = top + 18
        v = r["change_pct"]
        w = max(abs(v) / max_abs * half, 1.5)
        cls = "bar-pos" if v >= 0 else "bar-neg"
        # 기준선은 막대 구간에만 그린다 (이름 라벨을 가로지르지 않도록)
        parts.append(f'<line class="zero" x1="{mid}" y1="{bar_y - 3}" x2="{mid}" y2="{bar_y + bar_h + 3}"/>')
        if v >= 0:
            d = _bar_path(mid, mid + w, bar_y, bar_h, 4, "right")
            val_x, anchor = mid + w + 6, "start"
        else:
            d = _bar_path(mid - w, mid, bar_y, bar_h, 4, "left")
            val_x, anchor = mid - w - 6, "end"
        tip = (f"{r['name']} {r['date']}: {v:+.2f}% "
               f"(전일 {r['prev_value']:,.2f} → {r['value']:,.2f})")
        parts.append(
            f'<g><title>{escape(tip)}</title>'
            f'<path class="{cls}" d="{d}"/>'
            f'<text class="value" x="{val_x:.1f}" y="{bar_y + 15:.1f}" text-anchor="{anchor}">{v:+.2f}%</text>'
            f'</g>'
        )
        parts.append(
            f'<text class="label" x="4" y="{top + 12:.1f}">{escape(r["name"])}'
            f' <tspan class="sub">{escape(r["date"])}</tspan></text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
