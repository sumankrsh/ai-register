from ai_register.scanner import scan

from .conftest import write


def by_id(systems):
    return {s.id: s for s in systems}


def test_sample_repo_systems(sample_repo):
    systems = by_id(scan(sample_repo))
    assert set(systems) == {
        ".",
        "ml/churn-model",
        "services/cv-screener",
        "services/doc-search",
        "services/support-chatbot",
    }
    assert systems["services/cv-screener"].name == "cv-screener"  # from pyproject.toml
    assert systems["services/doc-search"].name == "doc-search"  # from package.json
    assert systems["services/doc-search"].providers == ["bedrock"]
    assert systems["services/doc-search"].vector_stores == ["pinecone"]
    assert systems["services/support-chatbot"].models == ["gpt-4o-mini"]
    assert systems["."].mcp_servers == ["crm-lookup", "filesystem"]
    assert "churn.onnx" in systems["ml/churn-model"].models


def test_skips_vendor_folders_and_excludes(tmp_path):
    write(tmp_path, "node_modules/openai/index.js", 'import OpenAI from "openai";')
    write(tmp_path, ".venv/lib/x.py", "import anthropic")
    write(tmp_path, "tests/test_x.py", "import anthropic")
    write(tmp_path, "app/main.py", "import anthropic")
    systems = scan(tmp_path, exclude=["tests"])
    files = {f.file for s in systems for f in s.findings}
    assert files == {"app/main.py"}


def test_files_without_manifest_belong_to_root(tmp_path):
    write(tmp_path, "scripts/tool.py", "import openai")
    systems = scan(tmp_path)
    assert [s.id for s in systems] == ["."]
    assert systems[0].name == tmp_path.name


def test_binary_and_huge_files_are_ignored(tmp_path):
    (tmp_path / "blob.py").write_bytes(b"import openai\x00\x01")
    write(tmp_path, "big.py", "import openai\n" + "x = 1\n" * 200_000)
    assert scan(tmp_path) == []


def test_notebook_code_cells(tmp_path):
    write(
        tmp_path,
        "nb.ipynb",
        '{"cells": [{"cell_type": "markdown", "source": ["import openai"]},'
        ' {"cell_type": "code", "source": ["from anthropic import Anthropic\\n"]}]}',
    )
    providers = {f.provider for s in scan(tmp_path) for f in s.findings}
    assert providers == {"anthropic"}


def test_not_a_folder(tmp_path):
    import pytest

    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "missing")
