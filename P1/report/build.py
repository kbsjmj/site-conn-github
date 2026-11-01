"""일일 시황 보고서 생성: 데이터 → 요약 → 차트 → HTML + manifest.json. PDF는 아직 만들지 않는다."""
import json
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from core.config import PROJECT

from . import summary
from .charts import change_bar_svg

KST = timezone(timedelta(hours=9))
TEMPLATE = PROJECT / "report" / "templates" / "daily_market.html"


def _fmt_date(d):
    return d or "-"


def build_daily(store, out_root, sources_used=("fred", "dart"), tier=1):
    if tier != 1:
        raise NotImplementedError("재배포 등급 2 이상은 license 검토 규칙을 구현한 뒤 사용합니다.")
    idx = summary.index_changes(store)
    disc = store.latest("disclosure", limit=10)

    as_of = max((r["date"] for r in idx), default=None) or datetime.now(KST).date().isoformat()
    generated = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    index_rows = "\n".join(
        f"      <tr><td>{escape(r['name'])}</td>"
        f"<td class=\"num\">{r['value']:,.2f}</td>"
        f"<td class=\"num\">{r['change_pct']:+.2f}%</td>"
        f"<td>{escape(r['date'])} / {escape(r['prev_date'])}</td></tr>"
        for r in idx
    ) or '      <tr><td colspan="4">지수 데이터 없음 (run을 먼저 실행하세요)</td></tr>'

    disc_rows = "\n".join(
        f"      <tr><td>{escape(_fmt_date(r['payload'].get('rcept_dt')))}</td>"
        f"<td>{escape(r['payload'].get('corp_name') or '-')}</td>"
        f"<td><a href=\"{escape(r['payload'].get('url') or '#')}\">{escape(r['payload'].get('report_nm') or '-')}</a></td></tr>"
        for r in disc
    ) or '      <tr><td colspan="3">공시 데이터 없음</td></tr>'

    html = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{AS_OF}}": escape(as_of),
        "{{GENERATED}}": escape(generated),
        "{{TIER}}": str(tier),
        "{{CHART}}": change_bar_svg(idx) or '<p class="note">차트를 그릴 데이터가 없습니다.</p>',
        "{{INDEX_ROWS}}": index_rows,
        "{{DISCLOSURE_ROWS}}": disc_rows,
        "{{SOURCES}}": escape(", ".join(sources_used)),
    }
    for k, v in replacements.items():
        html = html.replace(k, v)

    out_dir = Path(out_root) / as_of
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "daily_market.html"
    html_path.write_text(html, encoding="utf-8")

    manifest = {
        "report": "daily_market",
        "as_of": as_of,
        "generated_at": generated,
        "tier": tier,
        "sources": list(sources_used),
        "rows": {"index": len(idx), "disclosure": len(disc)},
        "files": ["daily_market.html"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"dir": str(out_dir), "html": str(html_path), "as_of": as_of, "index_rows": len(idx)}
