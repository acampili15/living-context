from warn import check_and_warn
from doc_format import WARN_MARKER, content_line_count


def _doc(n_lines: int) -> str:
    return "# CONTEXT\n\n" + "\n".join(f"line {i}" for i in range(n_lines)) + "\n"


def _doc_with_stale_banner(n_lines: int) -> str:
    """A doc whose *content* is n_lines long but which already carries the
    warn banner from some earlier run -- simulating a doc that shrank (or
    grew past threshold) without the banner having been recomputed yet.
    """
    return _doc(n_lines) + f"{WARN_MARKER}\n> stale banner text\n\n"


def test_missing_doc_is_a_noop(tmp_path):
    result = check_and_warn(tmp_path / "CONTEXT.md", threshold_lines=100, warn_ratio=0.85)
    assert result["skipped_reason"] == "doc does not exist"
    assert not result["warned"]


def test_under_warn_threshold_no_banner(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text(_doc(5))
    result = check_and_warn(doc, threshold_lines=100, warn_ratio=0.85)
    assert not result["warned"]
    assert not result["warning_cleared"]
    assert WARN_MARKER not in doc.read_text()


def test_in_warn_zone_adds_banner(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    # threshold=10, warn_ratio=0.5 -> warn at >=5 lines.
    doc.write_text(_doc(6))
    result = check_and_warn(doc, threshold_lines=10, warn_ratio=0.5)
    assert result["warned"] is True
    text = doc.read_text()
    assert WARN_MARKER in text
    assert "condense" in text


def test_at_hard_threshold_no_new_banner_added(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text(_doc(20))
    result = check_and_warn(doc, threshold_lines=10, warn_ratio=0.5)
    assert result["warned"] is False
    assert result["skipped_reason"] == "at or over hard threshold; deferring to archiving"
    assert WARN_MARKER not in doc.read_text()


def test_stale_banner_cleared_once_back_under_warn_zone(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    # Doc shrank back down (e.g. a manual condense) but still carries a
    # stale banner from before that -- it should be removed.
    doc.write_text(_doc_with_stale_banner(1))
    result = check_and_warn(doc, threshold_lines=10, warn_ratio=0.5)
    assert result["warning_cleared"] is True
    assert WARN_MARKER not in doc.read_text()


def test_stale_banner_cleared_when_doc_crosses_from_warn_zone_to_over_threshold(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    # Doc grew past the hard threshold without being archived down yet, but
    # still carries a stale warn-zone banner -- deferring to archiving means
    # this banner should be cleared, not left stale or duplicated.
    doc.write_text(_doc_with_stale_banner(20))
    result = check_and_warn(doc, threshold_lines=10, warn_ratio=0.5)
    assert result["skipped_reason"] == "at or over hard threshold; deferring to archiving"
    assert result["warning_cleared"] is True
    assert WARN_MARKER not in doc.read_text()


def test_reported_line_count_matches_content_line_count(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    text = _doc(6)
    doc.write_text(text)
    result = check_and_warn(doc, threshold_lines=10, warn_ratio=0.5)
    assert result["line_count"] == content_line_count(text)
