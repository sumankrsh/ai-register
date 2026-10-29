import shutil
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-repo"


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """A private copy of the synthetic sample repo that tests may modify."""
    target = tmp_path / "sample-repo"
    shutil.copytree(SAMPLE, target)
    return target


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    return path
