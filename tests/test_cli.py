from typer.testing import CliRunner

from ai_register.cli import app

from .conftest import write

runner = CliRunner()


def flat(text: str) -> str:
    return " ".join(text.split())


def test_scan_writes_register_and_reports(sample_repo, tmp_path):
    reg, md, html = tmp_path / "r.yaml", tmp_path / "r.md", tmp_path / "r.html"
    result = runner.invoke(app, ["scan", str(sample_repo), "-o", str(reg), "--report", str(md)])
    assert result.exit_code == 0, result.output
    assert "5 AI systems" in flat(result.output)
    assert reg.exists() and "## cv-screener" in md.read_text()
    result = runner.invoke(app, ["report", str(reg), "-o", str(html)])
    assert result.exit_code == 0
    page = html.read_text()
    assert page.startswith("<!doctype html>") and "Possibly high-risk" in page


def test_html_escapes_code_evidence(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "x.py", "import openai  # <script>alert(1)</script>\n")
    reg, html = tmp_path / "r.yaml", tmp_path / "r.html"
    assert runner.invoke(app, ["scan", str(repo), "-o", str(reg), "-r", str(html)]).exit_code == 0
    page = html.read_text()
    assert "<script>alert" not in page and "&lt;script&gt;" in page


def test_check_and_diff_exit_codes(sample_repo, tmp_path):
    reg = tmp_path / "r.yaml"
    assert runner.invoke(app, ["scan", str(sample_repo), "-o", str(reg)]).exit_code == 0
    assert runner.invoke(app, ["scan", str(sample_repo), "-o", str(reg), "--check"]).exit_code == 0
    clean = runner.invoke(app, ["diff", str(sample_repo), "--register", str(reg), "--fail-on-change"])
    assert clean.exit_code == 0 and "No changes" in flat(clean.output)

    write(sample_repo, "services/cv-screener/extra.py", "import openai\n")
    assert runner.invoke(app, ["scan", str(sample_repo), "-o", str(reg), "--check"]).exit_code == 1
    changed = runner.invoke(app, ["diff", str(sample_repo), "--register", str(reg), "--fail-on-change"])
    assert changed.exit_code == 1
    assert "provider added: openai" in flat(changed.output)


def test_check_without_register_fails(sample_repo, tmp_path):
    result = runner.invoke(app, ["scan", str(sample_repo), "-o", str(tmp_path / "none.yaml"), "--check"])
    assert result.exit_code == 1
    assert not (tmp_path / "none.yaml").exists()


def test_friendly_errors(tmp_path):
    missing = runner.invoke(app, ["scan", str(tmp_path / "nope"), "-o", str(tmp_path / "r.yaml")])
    assert missing.exit_code == 2 and "not a folder" in flat(missing.output)
    bad = tmp_path / "bad.yaml"
    bad.write_text("hello: world\n")
    result = runner.invoke(app, ["diff", str(tmp_path), "--register", str(bad)])
    assert result.exit_code == 2 and "not an ai-register file" in flat(result.output)
    assert runner.invoke(app, ["report", str(tmp_path / "x.yaml")]).exit_code == 2
