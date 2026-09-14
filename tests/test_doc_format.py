import doc_format as df


def test_split_entries_no_entries():
    text = "# CONTEXT\n\nSome preamble, no dated entries yet.\n"
    preamble, entries = df.split_entries(text)
    assert preamble == text
    assert entries == []


def test_split_entries_basic():
    text = (
        "# CONTEXT\n\npreamble\n\n"
        "## 2024-01-05 first entry\nbody one\n\n"
        "## 2024-02-10 second entry\nbody two\n"
    )
    preamble, entries = df.split_entries(text)
    assert preamble == "# CONTEXT\n\npreamble\n\n"
    assert [ym for ym, _ in entries] == ["2024-01", "2024-02"]
    assert entries[0][1] == "## 2024-01-05 first entry\nbody one\n\n"
    assert entries[1][1] == "## 2024-02-10 second entry\nbody two\n"


def test_split_entries_heading_requires_full_date():
    # A "## " heading that isn't YYYY-MM-DD shaped must not be treated as an entry.
    text = "# CONTEXT\n\n## Not A Date Heading\nsome text\n"
    preamble, entries = df.split_entries(text)
    assert preamble == text
    assert entries == []


def test_strip_block_removes_marker_and_blockquote_line():
    text = (
        f"{df.WARN_MARKER}\n> a warning line\n\n"
        "## 2024-01-05 entry\nbody\n"
    )
    stripped = df.strip_block(text, df.WARN_MARKER)
    assert df.WARN_MARKER not in stripped
    assert "a warning line" not in stripped
    assert stripped == "## 2024-01-05 entry\nbody\n"


def test_strip_block_no_marker_present_is_noop():
    text = "## 2024-01-05 entry\nbody\n"
    assert df.strip_block(text, df.WARN_MARKER) == text


def test_strip_known_blocks_removes_both_markers():
    text = (
        f"{df.POINTER_MARKER}\n> pointer line\n\n"
        f"{df.WARN_MARKER}\n> warning line\n\n"
        "## 2024-01-05 entry\nbody\n"
    )
    stripped = df.strip_known_blocks(text)
    assert df.POINTER_MARKER not in stripped
    assert df.WARN_MARKER not in stripped
    assert stripped == "## 2024-01-05 entry\nbody\n"


def test_content_line_count_excludes_instrumentation_blocks():
    bare = "line one\nline two\nline three"
    with_banner = f"{df.WARN_MARKER}\n> banner text\n\n" + bare
    assert df.content_line_count(with_banner) == df.content_line_count(bare)


def test_content_line_count_matches_manual_count():
    text = "a\nb\nc\n"
    # 3 newlines -> "a\nb\nc\n".count("\n") == 3, +1 == 4
    assert df.content_line_count(text) == 4


def test_rebuild_doc_assembles_preamble_blocks_and_entries():
    preamble = "# CONTEXT\n\nSome intro.\n"
    block = f"{df.POINTER_MARKER}\n> pointer\n\n"
    entries = [("2024-01", "## 2024-01-05 e\nbody\n")]
    result = df.rebuild_doc(preamble, [block], entries)
    assert result == "# CONTEXT\n\nSome intro.\n\n" + block + "## 2024-01-05 e\nbody\n"


def test_rebuild_doc_skips_empty_blocks():
    preamble = "# CONTEXT\n"
    entries = [("2024-01", "## 2024-01-05 e\nbody\n")]
    result = df.rebuild_doc(preamble, ["", ""], entries)
    assert result == "# CONTEXT\n\n## 2024-01-05 e\nbody\n"


def test_round_trip_split_then_rebuild_is_stable():
    text = (
        "# CONTEXT\n\npreamble\n\n"
        "## 2024-01-05 first\nbody one\n\n"
        "## 2024-02-10 second\nbody two\n"
    )
    preamble, entries = df.split_entries(text)
    assert df.rebuild_doc(preamble, [], entries) == text
