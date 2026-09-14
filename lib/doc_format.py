#!/usr/bin/env python3
"""Shared parsing/formatting for living-context docs. Both lib/archive.py
(mechanical archiving) and lib/warn.py (near-threshold banner) need to split
a doc into its preamble + dated entries, and both write a small sentinel-
marked block into that preamble -- this is the one place that logic lives,
so the two stay consistent and neither duplicates the entry-parsing regex.
"""
import re

ENTRY_HEADING_RE = re.compile(r"^## (\d{4}-\d{2})-\d{2}\b.*$", re.MULTILINE)

# The two sentinel-marked instrumentation blocks living-context writes into
# a doc's preamble. Defined once here (not in archive.py/warn.py) so that
# content_line_count below always strips exactly the blocks both modules
# know how to write -- a doc's size, for threshold purposes, is its actual
# entries/preamble prose, not living-context's own bookkeeping notes about
# that size. Without this, the warning banner's own lines could push a doc
# over threshold by themselves, which would be a confusing thing to explain.
POINTER_MARKER = "<!-- living-context:archive-pointer -->"
WARN_MARKER = "<!-- living-context:size-warning -->"
KNOWN_MARKERS = (POINTER_MARKER, WARN_MARKER)


def split_entries(text: str):
    """Split doc text into (preamble, [(year_month, entry_text), ...]).

    entry_text includes its own "## ..." heading line through (but not
    including) the next entry's heading, verbatim.
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


def make_block_re(marker: str) -> re.Pattern:
    """A regex matching this plugin's <marker>\\n> ...\\n\\n? block shape,
    so it can be stripped before a fresh one is regenerated -- every
    sentinel-marked block living-context writes (the archive pointer, the
    size warning) follows this same one-marker-line + one-blockquote-line
    shape, so a single helper covers all of them.
    """
    return re.compile(re.escape(marker) + r"\n>.*\n\n?", re.MULTILINE)


def strip_block(text: str, marker: str) -> str:
    return make_block_re(marker).sub("", text)


def strip_known_blocks(text: str) -> str:
    for marker in KNOWN_MARKERS:
        text = strip_block(text, marker)
    return text


def content_line_count(text: str) -> int:
    """Line count with all known instrumentation blocks stripped out --
    this is what threshold_lines/warn_ratio should always be compared
    against, everywhere, so a doc's own warning banner can't inflate the
    count that decides whether it needs a warning banner.
    """
    return strip_known_blocks(text).count("\n") + 1


def rebuild_doc(preamble: str, blocks: list, entries: list) -> str:
    """Reassemble preamble + sentinel blocks (in the order given) + entries
    into final doc text. `blocks` is a list of already-formatted block
    strings (each ending in its own blank-line separator, or empty string
    for "no block").
    """
    body = "".join(b for b in blocks if b)
    entry_text = "".join(e for _, e in entries)
    return preamble.rstrip("\n") + "\n\n" + body + entry_text
