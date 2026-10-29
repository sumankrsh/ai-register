"""Markdown and single-file HTML reports, grouped by system."""

from __future__ import annotations

from collections import Counter

from jinja2 import Environment, select_autoescape

from .register import DRAFT_NOTICE, effective_tier

TIER_LABEL = {
    "prohibited-candidate": "Possibly prohibited",
    "high-risk-candidate": "Possibly high-risk",
    "limited-risk": "Limited risk (transparency)",
    "minimal-risk": "Minimal risk",
}


def _where(finding: dict) -> str:
    return finding["file"] if not finding.get("line") else f"{finding['file']}:{finding['line']}"


def _cell(text: object) -> str:
    return str(text if text not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def summary(register: dict) -> dict:
    active = [s for s in register.get("systems", []) if s.get("lifecycle", "active") == "active"]
    tiers = Counter(effective_tier(s) for s in active)
    return {
        "systems": len(active),
        "not_detected": len(register.get("systems", [])) - len(active),
        "findings": sum(len(s.get("findings", [])) for s in active),
        "tiers": {t: tiers.get(t, 0) for t in TIER_LABEL},
        "unowned": sum(1 for s in active if not s.get("owner")),
        "open_controls": sum(1 for s in active for c in s.get("controls", []) if c.get("status") != "done"),
    }


def to_markdown(register: dict) -> str:
    stats = summary(register)
    out = [
        "# AI register",
        "",
        f"> {DRAFT_NOTICE}",
        "",
        f"Scanned `{register.get('scan_root', '?')}` at {register.get('generated_at', '?')} "
        f"with {register.get('generated_by', 'ai-register')}.",
        "",
        f"- AI systems found: **{stats['systems']}** ({stats['findings']} findings)",
        f"- Systems with no owner recorded: **{stats['unowned']}**",
        f"- Open controls: **{stats['open_controls']}**",
    ]
    if stats["not_detected"]:
        out.append(f"- Systems in the register that the scan no longer finds: **{stats['not_detected']}**")
    out += [
        "",
        "| System | Path | Providers | Models | Risk tier | Owner | Review |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in register.get("systems", []):
        tier = TIER_LABEL.get(effective_tier(s), effective_tier(s))
        if (s.get("risk") or {}).get("reviewed_tier"):
            tier += " (reviewed)"
        name = s.get("name", s["id"]) + (" (not detected)" if s.get("lifecycle") == "not-detected" else "")
        out.append(
            f"| {_cell(name)} | `{s['id']}` | {_cell(', '.join(s.get('providers') or []))} | "
            f"{_cell(', '.join(s.get('models') or []))} | {tier} | {_cell(s.get('owner'))} | "
            f"{_cell(s.get('review_status'))} |"
        )
    for s in register.get("systems", []):
        risk = s.get("risk") or {}
        out += [
            "",
            f"## {s.get('name', s['id'])}",
            "",
            f"Path: `{s['id']}`  ",
            f"Lifecycle: {s.get('lifecycle', 'active')}  ",
            f"Owner: {s.get('owner') or '_not recorded_'}  ",
            f"Purpose: {s.get('purpose') or '_not recorded_'}",
            "",
        ]
        if s.get("vector_stores"):
            out.append(f"Vector stores: {', '.join(s['vector_stores'])}  ")
        if s.get("mcp_servers"):
            out.append(f"MCP servers: {', '.join(s['mcp_servers'])}  ")
        if s.get("data_hints"):
            out.append(f"Data-handling hints: {', '.join(s['data_hints'])}")
        out += [
            "",
            "### Draft EU AI Act risk tier",
            "",
            f"**{TIER_LABEL.get(risk.get('draft_tier'), risk.get('draft_tier'))}** (draft)",
        ]
        if risk.get("reviewed_tier"):
            out.append(f"Reviewed tier: **{TIER_LABEL.get(risk['reviewed_tier'], risk['reviewed_tier'])}**")
        if risk.get("reviewer_notes"):
            out.append(f"Reviewer notes: {risk['reviewer_notes']}")
        out.append("")
        out += [f"- {line}" for line in risk.get("reasoning", [])]
        out += ["", "### ISO/IEC 42001 control checklist (draft)", ""]
        for c in s.get("controls", []):
            box = "x" if c.get("status") == "done" else " "
            evidence = f" Evidence: {c['evidence']}" if c.get("evidence") else ""
            out.append(f"- [{box}] **{c['id']} {c['title']}**: {c['why']}{evidence}")
        out += [
            "",
            "### Findings",
            "",
            "| Kind | Provider | Model | Where | Evidence | Hints |",
            "|---|---|---|---|---|---|",
        ]
        for f in s.get("findings", []):
            out.append(
                f"| {f['kind']} | {f['provider']} | {_cell(f.get('model'))} | `{_where(f)}` | "
                f"`{_cell(f.get('evidence'))}` | {_cell(', '.join(f.get('hints') or []))} |"
            )
    return "\n".join(out) + "\n"


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI register</title>
<style>
:root{--fg:#1d2330;--muted:#5a6375;--bg:#fbfbfd;--card:#fff;--line:#dfe3ea;--warn:#a33a00;--hi:#b3261e;--lim:#7a5b00;--min:#2f6b3a}
@media (prefers-color-scheme: dark){:root{--fg:#e6e9ef;--muted:#a3abba;--bg:#14171d;--card:#1c2028;--line:#323846;--warn:#ffb27a;--hi:#ff8a80;--lim:#f0d060;--min:#8fd19e}}
body{font:15px/1.5 system-ui,sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:24px 16px}
main{max-width:1100px;margin:auto}h1{margin:0 0 8px}h2{margin:32px 0 8px}
.notice{border-left:4px solid var(--warn);padding:8px 12px;background:var(--card);margin:12px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
code{font-size:12px;word-break:break-all}.muted{color:var(--muted)}
.tier{font-weight:600}.prohibited-candidate,.high-risk-candidate{color:var(--hi)}.limited-risk{color:var(--lim)}.minimal-risk{color:var(--min)}
ul.controls{list-style:none;padding:0}ul.controls li{margin:4px 0}
</style></head><body><main>
<h1>AI register</h1>
<p class="muted">Scanned <code>{{ r.scan_root }}</code> at {{ r.generated_at }} with {{ r.generated_by }}.</p>
<div class="notice">{{ notice }}</div>
<p>{{ s.systems }} AI systems, {{ s.findings }} findings. {{ s.unowned }} without an owner. {{ s.open_controls }} open controls.
{% if s.not_detected %}{{ s.not_detected }} no longer detected.{% endif %}</p>
<table><thead><tr><th>System</th><th>Path</th><th>Providers</th><th>Models</th><th>Risk tier</th><th>Owner</th></tr></thead><tbody>
{% for x in r.systems %}<tr><td><a href="#{{ x.id }}">{{ x.name }}</a>{% if x.lifecycle == 'not-detected' %} <span class="muted">(not detected)</span>{% endif %}</td>
<td><code>{{ x.id }}</code></td><td>{{ (x.providers or [])|join(', ') }}</td><td>{{ (x.models or [])|join(', ') }}</td>
<td class="tier {{ tier(x) }}">{{ labels.get(tier(x), tier(x)) }}{% if x.risk and x.risk.reviewed_tier %} (reviewed){% endif %}</td><td>{{ x.owner or '-' }}</td></tr>
{% endfor %}</tbody></table>
{% for x in r.systems %}<section class="card" id="{{ x.id }}"><h2>{{ x.name }}</h2>
<p class="muted">Path <code>{{ x.id }}</code> · {{ x.lifecycle }} · owner: {{ x.owner or 'not recorded' }} · purpose: {{ x.purpose or 'not recorded' }}</p>
{% if x.data_hints %}<p>Data-handling hints: {{ x.data_hints|join(', ') }}</p>{% endif %}
{% if x.mcp_servers %}<p>MCP servers: {{ x.mcp_servers|join(', ') }}</p>{% endif %}
<h3>Draft EU AI Act risk tier: <span class="tier {{ x.risk.draft_tier }}">{{ labels.get(x.risk.draft_tier, x.risk.draft_tier) }}</span></h3>
{% if x.risk.reviewed_tier %}<p>Reviewed tier: <b>{{ labels.get(x.risk.reviewed_tier, x.risk.reviewed_tier) }}</b> {{ x.risk.reviewer_notes or '' }}</p>{% endif %}
<ul>{% for line in x.risk.reasoning %}<li>{{ line }}</li>{% endfor %}</ul>
<h3>ISO/IEC 42001 control checklist (draft)</h3><ul class="controls">
{% for c in x.controls %}<li>{{ '☑' if c.status == 'done' else '☐' }} <b>{{ c.id }} {{ c.title }}</b>: {{ c.why }}{% if c.evidence %} <i>Evidence: {{ c.evidence }}</i>{% endif %}</li>{% endfor %}</ul>
<h3>Findings</h3><table><thead><tr><th>Kind</th><th>Provider</th><th>Model</th><th>Where</th><th>Evidence</th><th>Hints</th></tr></thead><tbody>
{% for f in x.findings %}<tr><td>{{ f.kind }}</td><td>{{ f.provider }}</td><td>{{ f.model or '' }}</td><td><code>{{ where(f) }}</code></td><td><code>{{ f.evidence }}</code></td><td>{{ (f.hints or [])|join(', ') }}</td></tr>
{% endfor %}</tbody></table></section>
{% endfor %}</main></body></html>
"""


def to_html(register: dict) -> str:
    env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
    template = env.from_string(HTML_TEMPLATE)
    return template.render(
        r=register,
        s=summary(register),
        notice=DRAFT_NOTICE,
        labels=TIER_LABEL,
        tier=effective_tier,
        where=_where,
    )
