#!/usr/bin/env python3
"""Shared config loading for living-context. Used by the hook worker and the
skill's scripts, so both sides agree on defaults and overrides without
duplicating them.

A consuming repo can override any default by adding
`.living-context/config.json` at its root. Nothing here requires that file
to exist -- living-context is zero-config by default.
"""
import json
import sys
from pathlib import Path

DEFAULTS = {
    # Main context doc, relative to repo root.
    "doc_path": "CONTEXT.md",
    # Directory (relative to repo root) that holds sub-feature docs the hook
    # may spawn when a commit's changes concentrate in one subtree.
    "sub_doc_dir": "context",
    # Directory (relative to repo root) that holds mechanically-archived
    # entries, grouped by the month they were originally written.
    "archive_dir": "context/archive",
    # When a doc (main or sub) exceeds this many lines after an append, the
    # hook mechanically moves its oldest entries into the archive.
    "threshold_lines": 400,
    # Once a doc's line count reaches this fraction of threshold_lines, the
    # hook writes a visible warning into the doc itself suggesting the user
    # run the skill's `condense` action -- a chance to consciously shorten
    # things before the mechanical (verbatim, not-shortened) archiving at
    # threshold_lines kicks in.
    "warn_ratio": 0.85,
    # If true, the hook commits its own doc/archive changes as a separate
    # commit after updating them. Default false: changes are left in the
    # working tree for the user to review and commit on their own terms --
    # an automation that commits on your behalf by default is the kind of
    # thing that should be opted into, not assumed.
    "auto_commit": False,
    # Model for the headless `claude -p` call. None means "use whatever
    # `claude -p` defaults to".
    "model": None,
}

CONFIG_RELATIVE_PATH = ".living-context/config.json"


def load_config(repo_root: Path) -> dict:
    """Return DEFAULTS merged with .living-context/config.json, if present.

    Unknown keys in the file are ignored (forward-compatible); a malformed
    file falls back to defaults rather than raising, since this is called
    from an unattended background hook that must never crash the caller.
    """
    config = dict(DEFAULTS)
    config_path = Path(repo_root) / CONFIG_RELATIVE_PATH
    if config_path.is_file():
        try:
            overrides = json.loads(config_path.read_text())
            for key in DEFAULTS:
                if key in overrides:
                    config[key] = overrides[key]
        except (json.JSONDecodeError, OSError):
            pass
    return config


def _main():
    if len(sys.argv) < 2 or sys.argv[1] != "show":
        print("usage: config.py show [repo_root]", file=sys.stderr)
        sys.exit(1)
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    config = load_config(repo_root)
    config_path = repo_root / CONFIG_RELATIVE_PATH
    print(f"Effective config for {repo_root}:")
    print(f"  (overrides file: {config_path}{'' if config_path.is_file() else ' -- not present, using defaults'})")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    _main()
