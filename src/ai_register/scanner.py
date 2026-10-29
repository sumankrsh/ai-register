"""Walk a codebase, collect findings and group them into systems."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .detectors import CODE, Finding, classify_path, mcp_servers, scan_text

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "site-packages",
    ".next",
    ".idea",
    ".vscode",
}
MANIFESTS = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
)
MAX_TEXT_BYTES = 1_000_000


@dataclass
class System:
    id: str  # posix path of the system folder relative to the scan root, "." for the root
    name: str
    findings: list[Finding] = field(default_factory=list)
    text_sample: list[tuple[str, int, str]] = field(default_factory=list)  # (file, line, text)
    mcp_servers: list[str] = field(default_factory=list)

    @property
    def providers(self) -> list[str]:
        skip = {"inline", "file", "local", "mcp", "unknown"}
        kinds = {"llm-sdk", "llm-call", "model-ref"}
        return sorted({f.provider for f in self.findings if f.kind in kinds and f.provider not in skip})

    @property
    def models(self) -> list[str]:
        names = {f.model for f in self.findings if f.model}
        names |= {PurePosixPath(f.file).name for f in self.findings if f.kind == "model-file"}
        return sorted(names)

    @property
    def vector_stores(self) -> list[str]:
        return sorted({f.provider for f in self.findings if f.kind == "vector-store"})

    @property
    def hints(self) -> list[str]:
        return sorted({h for f in self.findings for h in f.hints})


def _excluded(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(PurePosixPath(rel).name, p) for p in patterns)


def iter_files(root: Path, exclude: list[str] | None = None):
    """Yield (absolute path, posix path relative to root) in a stable order."""
    exclude = exclude or []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIRS
            and not d.endswith(".egg-info")
            and not _excluded(d if rel_dir == "." else f"{rel_dir}/{d}", exclude)
        )
        for name in sorted(filenames):
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            if not _excluded(rel, exclude):
                yield Path(dirpath) / name, rel


def _manifest_name(folder: Path) -> str | None:
    pyproject = folder / "pyproject.toml"
    if pyproject.is_file():
        try:
            name = tomllib.loads(pyproject.read_text("utf-8")).get("project", {}).get("name")
            if name:
                return str(name)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            pass
    package = folder / "package.json"
    if package.is_file():
        try:
            name = json.loads(package.read_text("utf-8")).get("name")
            if name:
                return str(name)
        except (ValueError, UnicodeDecodeError):
            pass
    return None


def system_folder(root: Path, rel_file: str, cache: dict[str, str]) -> str:
    """The nearest folder above a file that holds a project manifest, else the root."""
    parts = PurePosixPath(rel_file).parts[:-1]
    for depth in range(len(parts), 0, -1):
        candidate = "/".join(parts[:depth])
        if candidate not in cache:
            folder = root / candidate
            cache[candidate] = candidate if any((folder / m).is_file() for m in MANIFESTS) else ""
        if cache[candidate]:
            return cache[candidate]
    return "."


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def _notebook_source(text: str) -> str:
    """Join the code cells of a Jupyter notebook so line rules can run on it."""
    try:
        cells = json.loads(text).get("cells", [])
    except ValueError:
        return ""
    lines: list[str] = []
    for cell in cells:
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            lines.extend(("".join(source) if isinstance(source, list) else source).splitlines())
    return "\n".join(lines)


WORDS = re.compile(r"[A-Za-z][A-Za-z_\-]{2,}")


def scan(root: Path, exclude: list[str] | None = None) -> list[System]:
    """Scan a folder and return the systems that use AI, ordered by id."""
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a folder")
    cache: dict[str, str] = {}
    systems: dict[str, System] = {}
    texts: dict[str, list[tuple[str, int, str]]] = {}

    for path, rel in iter_files(root, exclude):
        folder = system_folder(root, rel, cache)
        suffix = path.suffix.lower()
        file_findings: list[Finding] = []
        text = None
        if suffix in CODE or suffix in (".json", ".md", ".txt", ".yaml", ".yml", ".prompt", ".prompty"):
            text = _read_text(path)
        whole = classify_path(rel, (text or "")[:20000])
        if whole:
            file_findings.append(whole)
        if text is not None and suffix in CODE:
            source = _notebook_source(text) if suffix == ".ipynb" else text
            file_findings.extend(scan_text(rel, source))
            texts.setdefault(folder, []).extend(
                (rel, n + 1, line) for n, line in enumerate(source.splitlines()) if WORDS.search(line)
            )
        elif text is not None and whole and whole.kind == "prompt-template":
            texts.setdefault(folder, []).extend((rel, n + 1, line) for n, line in enumerate(text.splitlines()))
        if not file_findings:
            continue
        system = systems.get(folder)
        if system is None:
            target = root if folder == "." else root / folder
            system = System(id=folder, name=_manifest_name(target) or target.name)
            systems[folder] = system
        system.findings.extend(file_findings)
        if whole and whole.kind == "mcp-config" and text:
            system.mcp_servers = sorted(set(system.mcp_servers) | set(mcp_servers(text)))

    for folder, system in systems.items():
        system.text_sample = texts.get(folder, [])
    return [systems[k] for k in sorted(systems)]
