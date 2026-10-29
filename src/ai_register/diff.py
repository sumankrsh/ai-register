"""Compare two registers so changes in AI usage show up in code review."""

from __future__ import annotations

from dataclasses import dataclass, field

from .detectors import Finding
from .register import effective_tier


@dataclass
class SystemChange:
    id: str
    name: str
    status: str  # added, removed, changed
    details: list[str] = field(default_factory=list)


@dataclass
class RegisterDiff:
    changes: list[SystemChange] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes

    def count(self, status: str) -> int:
        return sum(1 for c in self.changes if c.status == status)


def _active(register: dict) -> dict[str, dict]:
    return {s["id"]: s for s in register.get("systems", []) if s.get("lifecycle", "active") == "active"}


def _findings(entry: dict) -> dict[tuple, Finding]:
    found = [Finding.from_dict(f) for f in entry.get("findings", [])]
    return {f.key(): f for f in found}


def _list_change(label: str, old: list, new: list) -> list[str]:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    lines = [f"{label} added: {item}" for item in added]
    lines += [f"{label} removed: {item}" for item in removed]
    return lines


def _describe(f: Finding) -> str:
    where = f.file if f.line == 0 else f"{f.file}:{f.line}"
    model = f" model={f.model}" if f.model else ""
    return f"{f.kind} {f.provider}{model} at {where}"


def compare(old: dict, new: dict) -> RegisterDiff:
    before, after = _active(old), _active(new)
    result = RegisterDiff()
    for system_id in sorted(set(before) | set(after)):
        if system_id not in before:
            entry = after[system_id]
            details = [
                f"providers: {', '.join(entry.get('providers') or []) or 'none'}",
                f"draft tier: {effective_tier(entry)}",
            ]
            result.changes.append(SystemChange(system_id, entry.get("name", system_id), "added", details))
            continue
        if system_id not in after:
            entry = before[system_id]
            result.changes.append(SystemChange(system_id, entry.get("name", system_id), "removed"))
            continue
        a, b = before[system_id], after[system_id]
        details: list[str] = []
        old_tier, new_tier = effective_tier(a), effective_tier(b)
        if old_tier != new_tier:
            details.append(f"risk tier: {old_tier} -> {new_tier}")
        for key in ("providers", "models", "vector_stores", "mcp_servers", "data_hints"):
            details += _list_change(key.replace("_", " ").rstrip("s"), a.get(key) or [], b.get(key) or [])
        fa, fb = _findings(a), _findings(b)
        details += [f"new finding: {_describe(fb[k])}" for k in fb if k not in fa]
        details += [f"finding gone: {_describe(fa[k])}" for k in fa if k not in fb]
        if details:
            result.changes.append(SystemChange(system_id, b.get("name", system_id), "changed", details))
    return result
