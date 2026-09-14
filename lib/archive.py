#!/usr/bin/env python3
"""Mechanical, LLM-free archiving for living-context docs.

This is the one piece of automatic processing that touches *existing*
entries at all -- it moves the oldest ones out of the live doc once the doc
grows past a line-count threshold. It deliberately never asks an LLM to do
this: the whole point is that automatic processing must never paraphrase or
reword anything a human (or a prior hook run) already wrote. This script
only ever does exact text moves -- split the file into dated entries, cut
the oldest ones, paste them verbatim into a dated archive file. Nothing
about their wording changes.

Summarizing archived entries into something shorter *is* useful, but that's
a judgment call (which details still matter? does a correction still need
its original context to make sense?) that belongs to the skill's `condense`
action, run manually, with the result reviewed before it's committed. See
the plugin README's "Why archiving is automatic but condensing isn't"
section for the full rationale.
"""
import json
import re
import sys
from pathlib import Path

ENTRY_HEADING_RE = re.compile(r"^## (\d{4}-\d{2})-\d{2}\b.*$", re.MULTILINE)
POINTER_MARKER = "<!-- living-context:archive-pointer -->"
# Matches the marker line, the following blockquote line, and one trailing
# blank line, so re-inserting a freshly regenerated pointer never duplicates
# a stale one left by a previous run.
POINTER_BLOCK_RE = re.compile(
    re.escape(POINTER_MARKER) + r"\n>.*\n\n?", re.MULTILINE
)


def _split_entries(text: str):
    """Split doc text into (preamble, [(year_month, entry_text), ...]).

    entry_text includes its own "## ..." heading line through (but not
    including) the next entry's heading, verbatim -- exactly the bytes that
    will later be pasted into an archive file if this entry gets evicted.
    """
    matches = list(ENTRY_HEADING_RE.finditer(text))
    if not matches:
        return text, []
    preamble = text[: matches[0].start()]
    entries = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append((m.group(1), text[m.start():end]))
    return preamble, entries


def _strip_pointer(preamble: str) -> str:
    return POINTER_BLOCK_RE.sub("", preamble)


def archive_if_needed(doc_path: Path, archive_dir: Path, threshold_lines: int) -> dict:
    """Archive the oldest entries of doc_path if it's over threshold_lines.

    Returns a dict describing what happened, for logging. Never raises for
    "nothing to do" cases (missing file, under threshold, no parseable
    entries) -- those are all valid no-ops, not errors.
    """
    result = {"archived_entries": 0, "archive_files_touched": [], "skipped_reason": None}

    if not doc_path.is_file():
        result["skipped_reason"] = "doc does not exist"
        return result

    text = doc_path.read_text()
    if text.count("\n") + 1 <= threshold_lines:
        result["skipped_reason"] = "under threshold"
        return result

    preamble, entries = _split_entries(text)
    if len(entries) <= 1:
        result["skipped_reason"] = "not enough entries to archive (keeping the most recent one in place)"
        return result

    preamble = _strip_pointer(preamble)

    # Evict oldest entries (front of the list, since the format is
    # append-only-at-the-end / oldest-first) until we're back under
    # threshold, but always leave at least one entry live.
    evicted = []
    remaining = list(entries)
    while len(remaining) > 1:
        projected_lines = len(preamble.splitlines()) + sum(
            e.count("\n") + 1 for _, e in remaining
        )
        if projected_lines <= threshold_lines:
            break
        evicted.append(remaining.pop(0))

    if not evicted:
        result["skipped_reason"] = "single oldest entry alone exceeds threshold; left in place"
        return result

    # Group evicted entries by year-month and append verbatim to that
    # month's archive file.
    by_month = {}
    for year_month, entry_text in evicted:
        by_month.setdefault(year_month, []).append(entry_text)

    archive_dir.mkdir(parents=True, exist_ok=True)
    for year_month, blocks in by_month.items():
        archive_file = archive_dir / f"{year_month}.md"
        if not archive_file.is_file():
            archive_file.write_text(
                f"# Archived entries — {year_month}\n\n"
                "Moved verbatim from the live context doc by living-context's "
                "automatic archiving step. This step only ever cuts and pastes "
                "existing text -- nothing here has been reworded or "
                "summarized. See the `condense` skill action for that.\n\n"
            )
        with archive_file.open("a") as f:
            for block in blocks:
                f.write(block if block.endswith("\n") else block + "\n")
        result["archive_files_touched"].append(str(archive_file))

    # Regenerate the pointer line from the full current contents of
    # archive_dir, not just this run's additions, so it's always accurate
    # even if condense/manual edits changed what's there.
    archive_files = sorted(p.name for p in archive_dir.glob("*.md"))
    pointer = ""
    if archive_files:
        refs = ", ".join(f"`{archive_dir}/{name}`" for name in archive_files)
        pointer = f"{POINTER_MARKER}\n> Older entries archived to: {refs}\n\n"

    new_text = preamble.rstrip("\n") + "\n\n" + pointer + "".join(e for _, e in remaining)
    doc_path.write_text(new_text)

    result["archived_entries"] = len(evicted)
    return result


def _main():
    if len(sys.argv) != 4:
        print("usage: archive.py <doc_path> <archive_dir> <threshold_lines>", file=sys.stderr)
        sys.exit(1)
    doc_path = Path(sys.argv[1])
    archive_dir = Path(sys.argv[2])
    threshold_lines = int(sys.argv[3])
    result = archive_if_needed(doc_path, archive_dir, threshold_lines)
    print(json.dumps(result))


if __name__ == "__main__":
    _main()
