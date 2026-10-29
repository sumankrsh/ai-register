"""A starter ISO/IEC 42001 Annex A checklist for each system.

Control titles are short paraphrases of the Annex A headings, so check them
against your own copy of the standard. Which controls are listed depends on
what the scan found: a third-party model brings in supplier controls,
personal data nearby brings in data controls, and so on.
"""

from __future__ import annotations

from .scanner import System

A = {
    "A.3.2": "AI roles and responsibilities",
    "A.5.2": "AI system impact assessment process",
    "A.5.4": "Assessing impact on individuals or groups",
    "A.6.2.2": "AI system requirements and specification",
    "A.6.2.4": "AI system verification and validation",
    "A.6.2.6": "AI system operation and monitoring",
    "A.6.2.8": "AI system recording of event logs",
    "A.7.4": "Quality of data for AI systems",
    "A.7.5": "Data provenance",
    "A.8.2": "System documentation and information for users",
    "A.9.4": "Intended use of the AI system",
    "A.10.3": "Suppliers",
}


def checklist(system: System, tier: str) -> list[dict]:
    """Return controls as dicts: id, title, why, status, evidence."""
    items: list[tuple[str, str]] = [
        ("A.3.2", "Every AI system needs a named accountable owner."),
        ("A.9.4", "Record the intended use so the risk tier can be confirmed."),
        ("A.5.2", "An impact assessment is expected before go-live and after material change."),
        ("A.6.2.6", "Model behaviour should be monitored in production."),
    ]
    kinds = {f.kind for f in system.findings}
    hints = system.hints
    if system.providers or "mcp-config" in kinds:
        names = ", ".join(system.providers + (["MCP servers"] if "mcp-config" in kinds else []))
        items.append(
            (
                "A.10.3",
                f"Relies on third-party AI services or models ({names}); supplier terms and data use need review.",
            )
        )
    if any(h.startswith("pii:") for h in hints):
        fields = ", ".join(h[4:] for h in hints if h.startswith("pii:"))
        items.append(("A.5.4", f"Personal data appears near AI calls ({fields})."))
        items.append(("A.7.5", "Record where the personal data comes from and whether it may be sent to the model."))
    if "model-file" in kinds or "huggingface" in system.providers:
        items.append(
            ("A.6.2.4", "A self-hosted or open model is used; keep evaluation results for the version in use.")
        )
        items.append(("A.7.4", "Training or fine-tuning data quality should be documented."))
    if "vector-store" in kinds:
        items.append(("A.7.5", "Retrieved documents feed the model; record what is indexed and who owns it."))
    if "external-call" in hints or "mcp-config" in kinds:
        items.append(("A.6.2.8", "Calls leave the process; keep logs of prompts, tool calls and responses."))
    if tier in ("limited-risk", "high-risk-candidate", "prohibited-candidate"):
        items.append(("A.8.2", "People affected need clear information that they are dealing with AI."))
    if tier in ("high-risk-candidate", "prohibited-candidate"):
        items.append(("A.6.2.2", "High-risk candidates need documented requirements, including human oversight."))

    seen: dict[str, dict] = {}
    for control_id, why in items:
        if control_id in seen:
            seen[control_id]["why"] += " " + why
            continue
        seen[control_id] = {
            "id": control_id,
            "title": A[control_id],
            "why": why,
            "status": "open",
            "evidence": None,
        }
    return sorted(seen.values(), key=lambda c: [int(p) if p.isdigit() else p for p in c["id"][2:].split(".")])
