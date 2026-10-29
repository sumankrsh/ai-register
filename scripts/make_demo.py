"""Record real CLI output into docs/demo.svg.

Run from the project root:  python scripts/make_demo.py

It runs `ai-register scan` on the sample repo, then copies the sample repo to a
temporary folder, adds one new AI call and runs `ai-register diff` on the copy.
"""

from __future__ import annotations

import io
import os
import shlex
import shutil
import tempfile
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from ai_register import cli

ROOT = Path(__file__).resolve().parents[1]


def run(console: Console, command: str) -> None:
    """Run a command exactly as shown, from the current folder."""
    console.print(f"[bold green]$[/bold green] [bold]{command}[/bold]")
    result = CliRunner().invoke(cli.app, shlex.split(command)[1:])
    if result.exception and not isinstance(result.exception, SystemExit):
        raise result.exception
    console.print()


def main() -> None:
    console = Console(record=True, width=104, file=io.StringIO(), force_terminal=True)
    cli.console = console
    os.chdir(ROOT)
    run(console, "ai-register scan examples/sample-repo -o examples/ai-register.yaml --report examples/ai-register.md")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(ROOT / "examples", Path(tmp) / "examples")
        os.chdir(tmp)
        new = Path("examples/sample-repo/services/doc-search/src/summarise.ts")
        new.write_text(
            'import OpenAI from "openai";\n'
            "const client = new OpenAI();\n"
            "export const summarise = (text: string) =>\n"
            '  client.responses.create({ model: "gpt-4.1-mini", input: text });\n'
        )
        console.print("[dim]# a developer adds an OpenAI call to doc-search, then CI runs:[/dim]")
        run(console, "ai-register diff examples/sample-repo --register examples/ai-register.yaml --fail-on-change")
        os.chdir(ROOT)
    (ROOT / "docs").mkdir(exist_ok=True)
    console.save_svg(str(ROOT / "docs" / "demo.svg"), title="ai-register")
    print("wrote docs/demo.svg, examples/ai-register.yaml, examples/ai-register.md")


if __name__ == "__main__":
    main()
