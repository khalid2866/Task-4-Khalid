"""Tests for Phase 1 — input ingestion triage."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import ingestion
from reviewer.exceptions import (
    AccessDeniedError,
    FileMissingError,
    IngestionError,
)

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _write(tmp_path, name, data: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_whitespace_preserved_byte_for_byte(tmp_path):
    raw = b"def f():\r\n    x = 1  \n\treturn x\r\n"
    path = _write(tmp_path, "a.py", raw)
    ing = ingestion.ingest(path)
    assert ing.raw_text == raw.decode("utf-8")
    assert "\r\n" in ing.raw_text  # carriage returns preserved
    assert ing.raw_text.endswith("  \n") is False  # trailing spaces intact check below
    assert "x = 1  \n" in ing.raw_text


def test_missing_file_raises_clean_error(tmp_path):
    with pytest.raises(FileMissingError, match="does not point to a valid file"):
        ingestion.ingest(str(tmp_path / "nope.py"))


def test_directory_rejected(tmp_path):
    with pytest.raises(FileMissingError):
        ingestion.ingest(str(tmp_path))


def test_unsupported_extension_rejected(tmp_path):
    path = _write(tmp_path, "notes.txt", b"hello")
    with pytest.raises(IngestionError, match="unsupported extension"):
        ingestion.ingest(path)


def test_empty_file_rejected(tmp_path):
    path = _write(tmp_path, "empty.py", b"")
    with pytest.raises(IngestionError, match="empty"):
        ingestion.ingest(path)


def test_binary_asset_rejected(tmp_path):
    path = _write(tmp_path, "img.py", b"\x89PNG\r\n\x1a\n\x00\x01\x02")
    with pytest.raises(IngestionError, match="binary asset"):
        ingestion.ingest(path)


def test_unicode_fallback_no_crash(tmp_path):
    # latin-1 bytes that are invalid UTF-8 -> robust codec fallback.
    path = _write(tmp_path, "latin.py", b"# caf\xe9 au lait\nprint('hi')\n")
    ing = ingestion.ingest(path)
    assert ing.encoding_fallback is True
    assert "caf" in ing.raw_text
    assert any("fell back" in w for w in ing.warnings)


def test_language_detection(tmp_path):
    for name, lang in (("a.py", "python"), ("b.js", "javascript"), ("c.java", "java")):
        ing = ingestion.ingest(_write(tmp_path, name, b"x = 1\n"))
        assert ing.language == lang


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root bypasses file permission bits"
)
def test_permission_denied_rejected_safely(tmp_path):
    path = _write(tmp_path, "locked.py", b"x = 1\n")
    os.chmod(path, 0o000)
    try:
        with pytest.raises(AccessDeniedError, match="permission denied"):
            ingestion.ingest(path)
    finally:
        os.chmod(path, 0o644)


def test_sample_files_ingest():
    for name in ("buggy_example.py", "buggy_example.js", "buggy_example.java"):
        ing = ingestion.ingest(os.path.join(SAMPLES, name))
        assert ing.line_count > 5
        assert len(ing.sha256) == 64
