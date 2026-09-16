#!/usr/bin/env python3
"""PostToolUse hook entrypoint (fires after every Bash tool call).

This must return almost instantly -- it's on the critical path of every
Bash command the user runs, not just commits. All it does is: read the
hook's stdin JSON, decide in-process whether this was a successful `git
commit`, and if so, hand off to run_context_update.py as a detached
background process before exiting. It never waits for that process, and it
never raises -- any failure here should be invisible to the user's normal
workflow, not a scary error under an unrelated command.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Matches `git commit` as an actual subcommand invocation (optionally after
# `&&`/`;`/`|`, with optional leading whitespace, and optionally with flags
# like `-C <path>` before `commit`), not just the substring "git commit"
# appearing inside unrelated text. `commit` must be followed by whitespace
# or end-of-string (not just a word boundary) so a hyphenated lookalike
# subcommand name like `commit-msg-hook.sh` doesn't false-positive.
GIT_COMMIT_RE = re.compile(r"(?:^\s*|[;&|]\s*)git\s+(?:-\S+(?:\s+\S+)?\s+)*commit(?:\s|$)")


def _should_process(data: dict) -> bool:
    if data.get("tool_name") != "Bash":
        return False
    if data.get("tool_success", True) is False:
        return False
    command = (data.get("tool_input") or {}).get("command", "") or ""
    if "--dry-run" in command:
        return False
    return bool(GIT_COMMIT_RE.search(command))


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return

    try:
        if not _should_process(data):
            return

        cwd = data.get("cwd") or os.getcwd()
        worker = Path(__file__).resolve().parent / "run_context_update.py"

        # Resolve the actual repo root (the command may have run from a
        # subdirectory), and bail out quietly if this isn't a git repo at
        # all -- shouldn't happen given we just matched `git commit`, but a
        # background hook should never assume.
        try:
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd, capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return

        try:
            commit_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root, capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return

        # Detach fully: new session, stdio to /dev/null (the worker does its
        # own logging to CLAUDE_PLUGIN_DATA), so this process can exit
        # without waiting on it and without leaving a zombie tied to this
        # hook invocation.
        devnull = subprocess.DEVNULL
        subprocess.Popen(
            [sys.executable, str(worker), repo_root, commit_sha],
            stdin=devnull, stdout=devnull, stderr=devnull,
            start_new_session=True,
            env=os.environ.copy(),
        )
    except Exception:
        # Whatever goes wrong here, it must never surface as a failure of
        # the user's actual `git commit` -- this hook fires after the fact
        # and is pure bonus behavior.
        return


if __name__ == "__main__":
    main()
