import json
import subprocess
import sys

from conftest import PLUGIN_ROOT, git_commit, import_module_from_path

STATUS_SCRIPT = PLUGIN_ROOT / "skills" / "living-context" / "scripts" / "status.py"
status = import_module_from_path("living_context_status", STATUS_SCRIPT)


def test_doc_summary_missing_file(tmp_path):
    summary = status._doc_summary(tmp_path / "CONTEXT.md", threshold=400, warn_ratio=0.85)
    assert "does not exist yet" in summary


def test_doc_summary_reports_line_count_and_last_sha(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text(
        "# CONTEXT\n\n## 2024-01-05 entry\nsome update, commit `abc1234`\n"
    )
    summary = status._doc_summary(doc, threshold=400, warn_ratio=0.85)
    assert "abc1234" in summary
    assert "OVER THRESHOLD" not in summary
    assert "APPROACHING THRESHOLD" not in summary


def test_doc_summary_flags_over_threshold(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text("# CONTEXT\n\n" + "\n".join(f"line {i}" for i in range(50)) + "\n")
    summary = status._doc_summary(doc, threshold=10, warn_ratio=0.85)
    assert "OVER THRESHOLD" in summary


def test_doc_summary_flags_approaching_threshold_when_banner_present(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text(
        "# CONTEXT\n\n<!-- living-context:size-warning -->\n> This doc is 9/10 lines.\n\nbody\n"
    )
    summary = status._doc_summary(doc, threshold=10, warn_ratio=0.85)
    assert "APPROACHING THRESHOLD" in summary


def test_status_script_runs_cleanly_in_scratch_repo(git_repo):
    git_commit(git_repo, "initial commit")
    result = subprocess.run(
        [sys.executable, str(STATUS_SCRIPT)],
        cwd=git_repo, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "living-context status for" in result.stdout
    assert "does not exist yet" in result.stdout  # no CONTEXT.md written yet
    assert "sub-docs (0):" in result.stdout
    assert "archive (0 file(s)" in result.stdout


def test_status_script_reports_config_overrides(git_repo):
    config_dir = git_repo / ".living-context"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"threshold_lines": 123}))
    git_commit(git_repo, "initial commit")

    result = subprocess.run(
        [sys.executable, str(STATUS_SCRIPT)],
        cwd=git_repo, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "threshold_lines=123" in result.stdout


def test_status_script_fails_outside_git_repo(tmp_path):
    result = subprocess.run(
        [sys.executable, str(STATUS_SCRIPT)],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "Not inside a git repo" in result.stderr
