from archive import archive_if_needed
from doc_format import POINTER_MARKER


def _entry(date: str, lines: int) -> str:
    body = "\n".join(f"line {i}" for i in range(lines))
    return f"## {date} entry\n{body}\n\n"


def test_missing_doc_is_a_noop(tmp_path):
    result = archive_if_needed(tmp_path / "CONTEXT.md", tmp_path / "archive", threshold_lines=10)
    assert result["archived_entries"] == 0
    assert result["skipped_reason"] == "doc does not exist"


def test_under_threshold_is_a_noop(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text("# CONTEXT\n\n" + _entry("2024-01-01", 2))
    result = archive_if_needed(doc, tmp_path / "archive", threshold_lines=100)
    assert result["archived_entries"] == 0
    assert result["skipped_reason"] == "under threshold"
    assert doc.read_text() == "# CONTEXT\n\n" + _entry("2024-01-01", 2)


def test_single_entry_over_threshold_is_left_in_place(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    doc.write_text("# CONTEXT\n\n" + _entry("2024-01-01", 50))
    result = archive_if_needed(doc, tmp_path / "archive", threshold_lines=5)
    assert result["archived_entries"] == 0
    assert result["skipped_reason"] == "not enough entries to archive (keeping the most recent one in place)"


def test_evicts_oldest_entries_until_under_threshold(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "context" / "archive"
    text = "# CONTEXT\n\n" + _entry("2024-01-01", 3) + _entry("2024-01-02", 3) + _entry("2024-01-03", 3)
    doc.write_text(text)

    result = archive_if_needed(doc, archive_dir, threshold_lines=14)

    assert result["archived_entries"] == 1
    remaining = doc.read_text()
    assert "2024-01-01" not in remaining
    assert "2024-01-02" in remaining
    assert "2024-01-03" in remaining

    archive_file = archive_dir / "2024-01.md"
    assert archive_file.is_file()
    archived_text = archive_file.read_text()
    assert "2024-01-01" in archived_text
    # Verbatim: the archived entry text is untouched.
    assert _entry("2024-01-01", 3).strip("\n") in archived_text


def test_always_leaves_at_least_one_entry_live(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "archive"
    text = "# CONTEXT\n\n" + _entry("2024-01-01", 50) + _entry("2024-01-02", 50)
    doc.write_text(text)

    result = archive_if_needed(doc, archive_dir, threshold_lines=5)

    assert result["archived_entries"] == 1
    remaining_text = doc.read_text()
    assert "2024-01-01" not in remaining_text
    assert "2024-01-02" in remaining_text


def test_archived_entries_grouped_by_month_into_separate_files(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "archive"
    text = (
        "# CONTEXT\n\n"
        + _entry("2024-01-15", 3)
        + _entry("2024-02-15", 3)
        + _entry("2024-03-15", 3)
    )
    doc.write_text(text)

    result = archive_if_needed(doc, archive_dir, threshold_lines=8)

    assert result["archived_entries"] == 2
    assert (archive_dir / "2024-01.md").is_file()
    assert (archive_dir / "2024-02.md").is_file()
    assert not (archive_dir / "2024-03.md").is_file()


def test_pointer_line_written_and_lists_all_archive_files(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "context" / "archive"
    text = "# CONTEXT\n\n" + _entry("2024-01-01", 3) + _entry("2024-01-02", 3) + _entry("2024-01-03", 3)
    doc.write_text(text)

    archive_if_needed(doc, archive_dir, threshold_lines=8)

    remaining = doc.read_text()
    assert POINTER_MARKER in remaining
    assert "context/archive/2024-01.md" in remaining


def test_pointer_regenerated_from_full_archive_dir_contents(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    # A pre-existing archive file from an earlier run/condense, not created
    # by this call -- the pointer should still mention it.
    (archive_dir / "2023-12.md").write_text("# Archived entries — 2023-12\n\nold stuff\n")

    text = "# CONTEXT\n\n" + _entry("2024-01-01", 3) + _entry("2024-01-02", 3) + _entry("2024-01-03", 3)
    doc.write_text(text)

    archive_if_needed(doc, archive_dir, threshold_lines=8)

    remaining = doc.read_text()
    assert "2023-12.md" in remaining
    assert "2024-01.md" in remaining


def test_archiving_appends_to_existing_month_file_without_clobbering(tmp_path):
    doc = tmp_path / "CONTEXT.md"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "2024-01.md").write_text(
        "# Archived entries — 2024-01\n\n" + _entry("2024-01-01", 2)
    )

    text = "# CONTEXT\n\n" + _entry("2024-01-05", 3) + _entry("2024-01-10", 3) + _entry("2024-01-15", 3)
    doc.write_text(text)

    archive_if_needed(doc, archive_dir, threshold_lines=8)

    archived_text = (archive_dir / "2024-01.md").read_text()
    assert "2024-01-01" in archived_text
    assert "2024-01-05" in archived_text
