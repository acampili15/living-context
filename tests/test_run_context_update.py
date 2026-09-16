"""Integration tests for hooks/run_context_update.py.

These run the worker script as a real subprocess (the same way
context-update.py invokes it) against a real scratch git repo, with a fake
`claude` executable on PATH standing in for the real `claude -p` call --
the point of these tests is the orchestration (diff gathering, config
plumbing, archiving/warning passes, auto_commit, error handling), not the
LLM's drafting behavior, which isn't unit-testable (see the README's manual
"Verifying it's working" section for that).
"""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PLUGIN_ROOT, git_commit

WORKER = PLUGIN_ROOT / "hooks" / "run_context_update.py"

FAKE_CLAUDE_SCRIPT = """#!/usr/bin/env python3
import sys
with open("claude_invocation_args.json", "w") as f:
    import json
    json.dump(sys.argv[1:], f)
with open("CONTEXT.md", "a") as f:
    f.write("## 2024-01-01 stub entry\\nstub body from fake claude, commit `stub123`\\n\\n")
"""

FAKE_CLAUDE_FAILS_SCRIPT = """#!/usr/bin/env python3
import sys
sys.stderr.write("simulated claude failure\\n")
sys.exit(1)
"""


def _install_fake_claude(bin_dir: Path, script: str = FAKE_CLAUDE_SCRIPT):
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "claude"
    fake.write_text(script)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run_worker(repo_root: Path, commit_sha: str, log_dir: Path, path_dirs: list):
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(str(d) for d in path_dirs) + os.pathsep + env.get("PATH", "")
    env["CLAUDE_PLUGIN_DATA"] = str(log_dir)
    return subprocess.run(
        [sys.executable, str(WORKER), str(repo_root), commit_sha],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _log_text(log_dir: Path) -> str:
    log_file = log_dir / "context-update.log"
    return log_file.read_text() if log_file.is_file() else ""


def test_worker_appends_entry_via_claude_and_logs_completion(git_repo, tmp_path):
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    doc = git_repo / "CONTEXT.md"
    assert doc.is_file()
    assert "stub entry" in doc.read_text()

    log_text = _log_text(log_dir)
    assert f"commit={sha[:7]} starting" in log_text
    assert f"commit={sha[:7]} done" in log_text
    assert "claude -p exit=0" in log_text


def test_worker_passes_system_prompt_and_allowed_tools_to_claude(git_repo, tmp_path):
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    _run_worker(git_repo, sha, log_dir, [bin_dir])

    args = json.loads((git_repo / "claude_invocation_args.json").read_text())
    assert "-p" in args
    assert "--system-prompt-file" in args
    system_prompt_path = args[args.index("--system-prompt-file") + 1]
    assert system_prompt_path == str(PLUGIN_ROOT / "lib" / "prompts" / "system_prompt.md")
    assert "--allowed-tools" in args
    tools_index = args.index("--allowed-tools")
    assert args[tools_index + 1:tools_index + 5] == ["Read", "Write", "Edit", "Glob"]
    assert "Bash" not in args


def test_worker_handles_missing_claude_binary_gracefully(git_repo, tmp_path):
    sha = git_commit(git_repo, "add a feature")
    log_dir = tmp_path / "logs"

    # A minimal PATH that still resolves git/python (both needed by the
    # worker itself) but deliberately excludes wherever the real `claude`
    # CLI happens to live in this environment.
    git_dir = str(Path(shutil.which("git")).parent)
    python_dir = str(Path(shutil.which(sys.executable)).parent)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([git_dir, python_dir])
    assert shutil.which("claude", path=env["PATH"]) is None
    env["CLAUDE_PLUGIN_DATA"] = str(log_dir)
    result = subprocess.run(
        [sys.executable, str(WORKER), str(git_repo), sha],
        capture_output=True, text=True, timeout=30, env=env,
    )

    assert result.returncode == 0  # never raises/crashes visibly
    assert not (git_repo / "CONTEXT.md").is_file()
    log_text = _log_text(log_dir)
    assert "not found on PATH" in log_text


def test_worker_logs_claude_failure_and_does_not_append(git_repo, tmp_path):
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir, script=FAKE_CLAUDE_FAILS_SCRIPT)
    log_dir = tmp_path / "logs"

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0
    assert not (git_repo / "CONTEXT.md").is_file()
    log_text = _log_text(log_dir)
    assert "claude -p exit=1" in log_text
    assert "simulated claude failure" in log_text


def test_worker_respects_config_overrides(git_repo, tmp_path):
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"doc_path": "docs/NOTES.md"}))

    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir, script=(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "os.makedirs('docs', exist_ok=True)\n"
        "with open('docs/NOTES.md', 'a') as f:\n"
        "    f.write('## 2024-01-01 stub entry\\nbody, commit `stub123`\\n\\n')\n"
    ))
    log_dir = tmp_path / "logs"

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    assert (git_repo / "docs" / "NOTES.md").is_file()
    assert not (git_repo / "CONTEXT.md").is_file()


def test_worker_archives_over_threshold_doc_after_append(git_repo, tmp_path):
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"threshold_lines": 5, "warn_ratio": 0.5}))

    # Pre-seed CONTEXT.md with an old entry so there's something to evict
    # once the fake claude call appends one more and pushes it over 5 lines.
    (git_repo / "CONTEXT.md").write_text(
        "# CONTEXT\n\n"
        "## 2023-12-01 old entry\nold line one\nold line two\n\n"
    )
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    doc_text = (git_repo / "CONTEXT.md").read_text()
    assert "old entry" not in doc_text
    assert "stub entry" in doc_text
    archive_file = git_repo / "context" / "archive" / "2023-12.md"
    assert archive_file.is_file()
    assert "old entry" in archive_file.read_text()
    log_text = _log_text(log_dir)
    assert "archived 1 entries" in log_text


def test_worker_auto_commit_commits_when_archiving_touched_a_doc(git_repo, tmp_path):
    # touched_files is populated from what claude -p changed, plus whatever
    # archive_if_needed/check_and_warn additionally touch -- this exercises
    # the archiving-triggered path specifically (low threshold_lines, a
    # pre-existing old entry to evict).
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"auto_commit": True, "threshold_lines": 5, "warn_ratio": 0.5})
    )
    (git_repo / "CONTEXT.md").write_text(
        "# CONTEXT\n\n"
        "## 2023-12-01 old entry\nold line one\nold line two\n\n"
    )
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert after != before
    log_text = _log_text(log_dir)
    assert "auto-committed context update" in log_text
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "CONTEXT.md" not in status  # the doc's own changes got committed


def test_worker_auto_commit_succeeds_when_only_warn_banner_touched_a_doc(git_repo, tmp_path):
    # Regression test: when only the warn pass (not archiving) touches a
    # doc, archive_dir may never have been created on disk. auto_commit's
    # `git add` must not unconditionally include it in that case, or the
    # add fails on the nonexistent pathspec and aborts the whole commit.
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"auto_commit": True, "threshold_lines": 10, "warn_ratio": 0.1})
    )

    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"
    assert not (git_repo / "context" / "archive").exists()

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert after != before
    log_text = _log_text(log_dir)
    assert "auto-committed context update" in log_text
    assert "commit failed" not in log_text
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "CONTEXT.md" not in status


def test_worker_auto_commit_commits_a_plain_append(git_repo, tmp_path):
    # Regression test: touched_files must include doc_path itself once
    # claude -p appends to it, even when the append doesn't also cross the
    # archive/warn thresholds in the same run -- otherwise auto_commit never
    # fires on an ordinary commit, contrary to what the README describes
    # ("the hook commits its own doc/archive changes").
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"auto_commit": True}))

    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert after != before  # auto-commit happened
    log_text = _log_text(log_dir)
    assert "auto-committed context update" in log_text
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "CONTEXT.md" not in status  # the appended entry got committed
    show = subprocess.run(
        ["git", "show", "--stat", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "CONTEXT.md" in show


def test_worker_no_commit_left_dirty_when_auto_commit_disabled(git_repo, tmp_path):
    sha = git_commit(git_repo, "add a feature")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    _run_worker(git_repo, sha, log_dir, [bin_dir])

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "CONTEXT.md" in status  # left for the user to review/commit themselves


def test_worker_handles_root_commit_with_no_parent(git_repo, tmp_path):
    # git_commit's very first commit in a fresh repo has no parent -- the
    # worker must use `git show` rather than `git diff <sha>^ <sha>` here.
    sha = git_commit(git_repo, "initial commit")
    bin_dir = tmp_path / "bin"
    _install_fake_claude(bin_dir)
    log_dir = tmp_path / "logs"

    result = _run_worker(git_repo, sha, log_dir, [bin_dir])

    assert result.returncode == 0, result.stderr
    assert (git_repo / "CONTEXT.md").is_file()
    log_text = _log_text(log_dir)
    assert "could not read diff" not in log_text
