#!/usr/bin/env python3
"""The actual work of a context update, run detached/in the background by
context-update.py so the triggering `git commit` never waits on it.

Flow: gather this commit's message + diff -> ask a headless `claude -p` call
(scoped to Read/Write/Edit/Glob only, no Bash, no network) to append a
grounded entry to the right doc, per lib/prompts/system_prompt.md's rules
-> mechanically archive any doc that's now over its line threshold (pure
Python, no LLM -- see lib/archive.py) -> optionally auto-commit, if the repo
opted into that.

Everything here is best-effort: a failure partway through (claude binary
missing, a timeout, a git error) should just stop and log, never raise
somewhere that could look like a crash of anything the user is doing --
this process has no attached terminal and nothing is waiting on its exit
code.
"""
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from config import load_config  # noqa: E402
from archive import archive_if_needed  # noqa: E402

MAX_DIFF_CHARS = 20_000
CLAUDE_TIMEOUT_SECONDS = 180


def _log_dir() -> Path:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(data_dir) if data_dir else Path.home() / ".living-context" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _log(log_file: Path, message: str):
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with log_file.open("a") as f:
        f.write(f"[{timestamp}] {message}\n")


def _git(repo_root: str, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=10, check=True,
    ).stdout


def main():
    if len(sys.argv) != 3:
        return
    repo_root, commit_sha = sys.argv[1], sys.argv[2]
    short_sha = commit_sha[:7]

    log_file = _log_dir() / "context-update.log"
    _log(log_file, f"repo={repo_root} commit={short_sha} starting")

    try:
        config = load_config(Path(repo_root))
        doc_path = Path(repo_root) / config["doc_path"]
        sub_doc_dir = Path(repo_root) / config["sub_doc_dir"]
        archive_dir = Path(repo_root) / config["archive_dir"]
        threshold = int(config["threshold_lines"])

        try:
            commit_message = _git(repo_root, "log", "-1", "--format=%B", commit_sha).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            _log(log_file, f"could not read commit message: {e}")
            return

        try:
            # Include parent for context; --root handles the repo's first commit.
            has_parent = subprocess.run(
                ["git", "rev-parse", f"{commit_sha}^"],
                cwd=repo_root, capture_output=True, timeout=5,
            ).returncode == 0
            diff_args = ["show", commit_sha] if not has_parent else ["diff", f"{commit_sha}^", commit_sha]
            diff = _git(repo_root, *diff_args)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            _log(log_file, f"could not read diff: {e}")
            return

        truncated = len(diff) > MAX_DIFF_CHARS
        if truncated:
            diff = diff[:MAX_DIFF_CHARS] + "\n[... diff truncated at {} characters ...]".format(MAX_DIFF_CHARS)

        user_prompt = (
            f"Commit: {short_sha}\n"
            f"Message:\n{commit_message}\n\n"
            f"Diff{' (truncated)' if truncated else ''}:\n{diff}\n\n"
            f"Main doc path (relative to repo root): {config['doc_path']}\n"
            f"Sub-doc directory (relative to repo root): {config['sub_doc_dir']}\n"
            "Follow the rules in your system prompt. Decide skip-or-log, then "
            "if logging, use your Read/Glob/Write/Edit tools to append the entry."
        )

        cmd = [
            "claude", "-p", user_prompt,
            "--system-prompt-file", str(PLUGIN_ROOT / "lib" / "prompts" / "system_prompt.md"),
            "--allowed-tools", "Read", "Write", "Edit", "Glob",
        ]
        if config.get("model"):
            cmd += ["--model", config["model"]]

        start = time.time()
        try:
            proc = subprocess.run(
                cmd, cwd=repo_root, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            _log(log_file, f"claude -p timed out after {CLAUDE_TIMEOUT_SECONDS}s")
            return
        except FileNotFoundError:
            _log(log_file, "`claude` executable not found on PATH -- cannot run context update")
            return

        elapsed = time.time() - start
        _log(log_file, f"claude -p exit={proc.returncode} elapsed={elapsed:.1f}s")
        if proc.returncode != 0:
            _log(log_file, f"stderr: {proc.stderr[-2000:]}")
            return
        if proc.stdout.strip():
            _log(log_file, f"stdout: {proc.stdout.strip()[-2000:]}")

        # Mechanical archiving pass -- no LLM involved from here on. Check
        # the main doc plus every sub-doc that exists, since any of them
        # could have just been appended to (or could have grown past
        # threshold from earlier runs even without this one touching them).
        archive_targets = [doc_path]
        if sub_doc_dir.is_dir():
            archive_targets += sorted(sub_doc_dir.glob("*.md"))

        touched_files = []
        for target in archive_targets:
            result = archive_if_needed(target, archive_dir, threshold)
            if result["archived_entries"]:
                touched_files.append(str(target))
                _log(
                    log_file,
                    f"archived {result['archived_entries']} entries from {target} "
                    f"into {result['archive_files_touched']}",
                )

        if config.get("auto_commit") and touched_files:
            try:
                _git(repo_root, "add", *touched_files, str(archive_dir))
                _git(
                    repo_root, "commit", "-m",
                    f"context: update after {short_sha}",
                )
                _log(log_file, f"auto-committed context update for {short_sha}")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                _log(log_file, f"auto_commit enabled but commit failed: {e}")

        _log(log_file, f"repo={repo_root} commit={short_sha} done")
    except Exception as e:  # noqa: BLE001 -- last-resort catch for a detached background job
        _log(log_file, f"unexpected error: {e!r}")


if __name__ == "__main__":
    main()
