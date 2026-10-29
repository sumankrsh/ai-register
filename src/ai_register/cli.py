"""Command line interface: scan, diff, report."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .diff import compare
from .register import build, effective_tier, load, save
from .report import TIER_LABEL, summary, to_html, to_markdown
from .scanner import scan as scan_folder

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Keep a register of the AI systems in your code, ready for governance review.",
)
console = Console()

TIER_STYLE = {
    "prohibited-candidate": "bold red",
    "high-risk-candidate": "red",
    "limited-risk": "yellow",
    "minimal-risk": "green",
}

ExcludeOpt = Annotated[
    list[str] | None,
    typer.Option("--exclude", "-x", help="Glob of files or folders to skip. Repeatable."),
]


def _fail(message: str) -> None:
    console.print(f"[red]error:[/red] {message}")
    raise typer.Exit(2)


def _scan(path: Path, exclude: list[str] | None, previous: dict | None) -> dict:
    try:
        systems = scan_folder(path, exclude)
    except NotADirectoryError as exc:
        _fail(str(exc))
    return build(systems, path.as_posix(), previous)


def _load_optional(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return load(path)
    except (ValueError, OSError) as exc:
        _fail(str(exc))


def _write_report(register: dict, target: Path, fmt: str | None = None) -> None:
    fmt = fmt or ("html" if target.suffix.lower() in (".html", ".htm") else "md")
    if fmt not in ("md", "html"):
        _fail(f"unknown report format {fmt!r}; use md or html")
    target.write_text(to_html(register) if fmt == "html" else to_markdown(register), "utf-8")


def _print_table(register: dict) -> None:
    table = Table(title="AI register (draft)", title_justify="left", header_style="bold")
    for column in ("System", "Providers", "Models", "Draft risk tier", "Owner"):
        table.add_column(column, overflow="fold")
    for s in register["systems"]:
        tier = effective_tier(s)
        name = s.get("name", s["id"])
        if s.get("lifecycle") == "not-detected":
            name += " [dim](not detected)[/dim]"
        table.add_row(
            f"{name}\n[dim]{s['id']}[/dim]",
            ", ".join(s.get("providers") or []) or "-",
            ", ".join(s.get("models") or []) or "-",
            f"[{TIER_STYLE.get(tier, '')}]{TIER_LABEL.get(tier, tier)}[/]",
            s.get("owner") or "[dim]not recorded[/dim]",
        )
    console.print(table)


def _strip_volatile(register: dict) -> dict:
    return {k: v for k, v in register.items() if k not in ("generated_at", "generated_by")}


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="Folder to scan.")] = Path("."),
    output: Annotated[Path, typer.Option("--output", "-o", help="Register file to write or update.")] = Path(
        "ai-register.yaml"
    ),
    report: Annotated[Path | None, typer.Option("--report", "-r", help="Also write a report (.md or .html).")] = None,
    exclude: ExcludeOpt = None,
    check: Annotated[
        bool, typer.Option("--check", help="Write nothing; exit 1 if the register is out of date.")
    ] = False,
) -> None:
    """Scan a codebase for AI usage and write or update the register."""
    previous = _load_optional(output)
    register = _scan(path, exclude, previous)
    if check:
        if previous is not None and _strip_volatile(previous) == _strip_volatile(register):
            console.print(f"[green]{output} is up to date.[/green]")
            return
        console.print(
            f"[red]{output} is out of date.[/red] Run: ai-register scan {path.as_posix()} -o {output.as_posix()}"
        )
        raise typer.Exit(1)
    save(register, output)
    _print_table(register)
    stats = summary(register)
    tiers = ", ".join(f"{n} {TIER_LABEL[t].lower()}" for t, n in stats["tiers"].items() if n)
    console.print(
        f"{stats['systems']} AI systems, {stats['findings']} findings ({tiers or 'none'}). "
        f"{stats['unowned']} without an owner, {stats['open_controls']} open controls."
    )
    if stats["not_detected"]:
        console.print(
            f"[yellow]{stats['not_detected']} systems in the register were not found this time and are marked not-detected.[/yellow]"
        )
    if report:
        _write_report(register, report)
    console.print(f"Wrote [bold]{output}[/bold]" + (f" and [bold]{report}[/bold]" if report else ""))
    console.print("[dim]Risk tiers and controls are drafts for a human reviewer, not legal advice.[/dim]")


@app.command()
def diff(
    path: Annotated[Path, typer.Argument(help="Folder to scan.")] = Path("."),
    register_file: Annotated[Path, typer.Option("--register", help="Existing register to compare against.")] = Path(
        "ai-register.yaml"
    ),
    exclude: ExcludeOpt = None,
    fail_on_change: Annotated[
        bool, typer.Option("--fail-on-change", help="Exit 1 when anything changed (for CI).")
    ] = False,
) -> None:
    """Show how AI usage in the code differs from the register."""
    if not register_file.exists():
        _fail(f"{register_file} not found; run 'ai-register scan' first")
    old = _load_optional(register_file)
    new = _scan(path, exclude, old)
    result = compare(old, new)
    if result.empty:
        console.print(f"[green]No changes against {register_file}.[/green]")
        return
    style = {"added": "green", "removed": "red", "changed": "yellow"}
    for change in result.changes:
        console.print(f"[{style[change.status]}]{change.status.upper():8}[/] [bold]{change.name}[/bold] ({change.id})")
        for line in change.details:
            console.print(f"           {line}")
    console.print(
        f"{result.count('added')} added, {result.count('removed')} removed, {result.count('changed')} changed. "
        f"Run 'ai-register scan' to update {register_file}."
    )
    if fail_on_change:
        raise typer.Exit(1)


@app.command()
def report(
    register_file: Annotated[Path, typer.Argument(help="Register file to render.")] = Path("ai-register.yaml"),
    output: Annotated[Path, typer.Option("--output", "-o", help="Report file (.md or .html).")] = Path(
        "ai-register.md"
    ),
    fmt: Annotated[str | None, typer.Option("--format", "-f", help="md or html; default from the file suffix.")] = None,
) -> None:
    """Render a register as a Markdown or HTML report."""
    if not register_file.exists():
        _fail(f"{register_file} not found")
    register = _load_optional(register_file)
    _write_report(register, output, fmt)
    console.print(f"Wrote [bold]{output}[/bold]")


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"ai-register {__version__}")


def main() -> None:
    app()
