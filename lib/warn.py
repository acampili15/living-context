#!/usr/bin/env python3
"""Near-threshold size warning for living-context docs.

Runs after archive.py's mechanical archiving pass, so it only ever sees a
doc that's already been brought under threshold_lines if that was possible.
Its job is different from archiving: archiving is the safety net that
*must* keep a doc bounded; this is an earlier, softer nudge -- "you're
getting close, consider running `condense` yourself" -- so the user gets a
chance to consciously shorten things instead of just letting verbatim
archiving happen to them silently.

Like archive.py, this never rewrites entry text -- it only adds or removes
its own small sentinel-marked banner line near the top of the doc.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_format import (  # noqa: E402
    split_entries, strip_block, content_line_count, rebuild_doc, WARN_MARKER,
)


def check_and_warn(doc_path: Path, threshold_lines: int, warn_ratio: float) -> dict:
    """Add or remove the size-warning banner in doc_path based on its
    current line count vs. warn_ratio * threshold_lines.

    Returns a dict describing what happened, for logging. A no-op (doc
    missing, doc not in the warn zone, banner already correct) is not an
    error. The line count used for the decision excludes living-context's
    own instrumentation blocks (the pointer line, this banner itself) --
    otherwise the banner's own lines could push a doc over threshold by
    themselves, which would be a confusing thing to have happen.
    """
    result = {"warned": False, "warning_cleared": False, "line_count": 0, "skipped_reason": None}

    if not doc_path.is_file():
        result["skipped_reason"] = "doc does not exist"
        return result

    text = doc_path.read_text()
    had_banner = WARN_MARKER in text
    line_count = content_line_count(text)
    result["line_count"] = line_count
    warn_threshold = warn_ratio * threshold_lines

    preamble, entries = split_entries(text)
    clean_preamble = strip_block(preamble, WARN_MARKER)

    if line_count >= threshold_lines:
        # Already over the hard threshold -- archive.py should have already
        # brought this down (it runs first); if it couldn't (e.g. a single
        # oversized entry), a size banner on top of that isn't the useful
        # signal here, so leave it alone rather than add noise.
        result["skipped_reason"] = "at or over hard threshold; deferring to archiving"
        if had_banner:
            doc_path.write_text(rebuild_doc(clean_preamble, [], entries))
            result["warning_cleared"] = True
        return result

    if line_count >= warn_threshold:
        banner = (
            f"{WARN_MARKER}\n"
            f"> This doc is {line_count}/{threshold_lines} lines -- approaching the "
            "point where old entries get mechanically archived. Consider running "
            "the living-context skill's `condense` action soon, so shortening is "
            "a deliberate choice rather than automatic archiving.\n\n"
        )
        doc_path.write_text(rebuild_doc(clean_preamble, [banner], entries))
        result["warned"] = True
        return result

    # Under the warn zone -- make sure no stale banner lingers (e.g. after
    # a manual condense brought the doc back down).
    if had_banner:
        doc_path.write_text(rebuild_doc(clean_preamble, [], entries))
        result["warning_cleared"] = True
    else:
        result["skipped_reason"] = "under warn threshold"
    return result


def _main():
    if len(sys.argv) != 4:
        print("usage: warn.py <doc_path> <threshold_lines> <warn_ratio>", file=sys.stderr)
        sys.exit(1)
    doc_path = Path(sys.argv[1])
    threshold_lines = int(sys.argv[2])
    warn_ratio = float(sys.argv[3])
    result = check_and_warn(doc_path, threshold_lines, warn_ratio)
    print(json.dumps(result))


if __name__ == "__main__":
    _main()
