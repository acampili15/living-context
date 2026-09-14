"""Shared fixtures for living-context's test suite.

The hook scripts under hooks/ have hyphenated filenames (context-update.py)
so they can't be imported as normal modules -- import_module_from_path
below loads them by file path instead. Everything under lib/ is a regular
importable module (pyproject.toml adds lib/ to pythonpath), so tests for
lib/*.py just `import config`, `import doc_format`, etc. directly.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def import_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def git_repo(tmp_path):
    """An initialized, empty git repo in tmp_path, with a committer identity
    configured so `git commit` works non-interactively.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test User")
    return repo


def git_commit(repo: Path, message: str, *, filename: str = "file.txt", content: str = "content\n") -> str:
    """Write `content` to `filename` in `repo`, commit it, and return the
    resulting commit SHA.
    """
    (repo / filename).write_text(content)
    subprocess.run(["git", "add", filename], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message], cwd=repo, check=True, capture_output=True,
    )
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()
