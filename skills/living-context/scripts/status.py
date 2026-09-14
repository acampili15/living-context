#!/usr/bin/env python3
"""Prints a human-readable status summary for the living-context setup in
the current repo: doc sizes vs. threshold, the last commit each doc was
updated for, and what sub-docs/archive files exist. Read-only -- makes no
changes.
"""
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from config import load_config, CONFIG_RELATIVE_PATH  # noqa: E402

LAST_SHA_RE = re.compile(r"commit `([0-9a-f]{7,40})`")


def _repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
    )
    if out.returncode != 0:
        print("Not inside a git repo.", file=sys.stderr)
        sys.exit(1)
    return Path(out.stdout.strip())


def _doc_summary(path: Path, threshold: int) -> str:
    if not path.is_file():
        return f"  {path}: does not exist yet (will be created on the next logged commit)"
    text = path.read_text()
    line_count = text.count("\n") + 1
    matches = LAST_SHA_RE.findall(text)
    last_sha = matches[-1] if matches else "none found"
    over = " (OVER THRESHOLD -- will be archived on next hook run)" if line_count > threshold else ""
    return f"  {path}: {line_count} lines / {threshold} threshold{over}, last entry commit `{last_sha}`"


def main():
    repo_root = _repo_root()
    config = load_config(repo_root)
    config_path = repo_root / CONFIG_RELATIVE_PATH
    threshold = int(config["threshold_lines"])

    print(f"living-context status for {repo_root}\n")
    print(f"config: {config_path}{'' if config_path.is_file() else ' (not present -- using defaults)'}")
    print(f"  doc_path={config['doc_path']}  sub_doc_dir={config['sub_doc_dir']}  "
          f"archive_dir={config['archive_dir']}  threshold_lines={threshold}  "
          f"auto_commit={config['auto_commit']}\n")

    print("main doc:")
    print(_doc_summary(repo_root / config["doc_path"], threshold))

    sub_doc_dir = repo_root / config["sub_doc_dir"]
    sub_docs = sorted(p for p in sub_doc_dir.glob("*.md")) if sub_doc_dir.is_dir() else []
    print(f"\nsub-docs ({len(sub_docs)}):")
    if not sub_docs:
        print("  none")
    for p in sub_docs:
        print(_doc_summary(p, threshold))

    archive_dir = repo_root / config["archive_dir"]
    archive_files = sorted(archive_dir.glob("*.md")) if archive_dir.is_dir() else []
    print(f"\narchive ({len(archive_files)} file(s) under {archive_dir}):")
    if not archive_files:
        print("  none")
    for p in archive_files:
        entry_count = p.read_text().count("\n## ") + (1 if p.read_text().startswith("## ") else 0)
        print(f"  {p}: {entry_count} archived entries")

    log_hint = "$CLAUDE_PLUGIN_DATA/context-update.log (or ~/.living-context/logs/ if that's unset)"
    print(f"\nHook run log: {log_hint}")


if __name__ == "__main__":
    main()
