"""Tests for the end-to-end IPO pipeline."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import pipeline
from reviewer.exceptions import EngineError, FileMissingError, ReviewerError

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_end_to_end_python(tmp_path):
    res = pipeline.run_review(
        os.path.join(SAMPLES, "buggy_example.py"),
        engine="demo",
        mode="review",
        plain=True,
        render=False,
        save_dir=str(tmp_path),
    )
    assert list(pipeline.STAGES) == [s.stage for s in res.stages]
    assert all(s.status == "ok" for s in res.stages)
    assert "## BUG_REPORT" in res.report
    assert res.report_path and os.path.exists(res.report_path)
    assert res.manifest_path and os.path.exists(res.manifest_path)
    manifest = json.load(open(res.manifest_path))
    assert manifest["language"] == "python"
    assert manifest["engine"] == "demo"


def test_end_to_end_js_and_java():
    for name, lang in (("buggy_example.js", "javascript"), ("buggy_example.java", "java")):
        res = pipeline.run_review(
            os.path.join(SAMPLES, name), engine="demo", render=False
        )
        assert res.language == lang
        assert "## REFACTORED_CODE" in res.report


def test_explain_mode_end_to_end():
    res = pipeline.run_review(
        os.path.join(SAMPLES, "buggy_example.py"),
        engine="demo",
        mode="explain",
        render=False,
    )
    assert res.report.startswith("## EXPLANATION")


def test_missing_file_raises_reviewer_error():
    with pytest.raises(FileMissingError):
        pipeline.run_review("/nonexistent/x.py", engine="demo", render=False)


def test_unknown_engine_rejected():
    with pytest.raises(EngineError, match="Unknown engine"):
        pipeline.run_review(
            os.path.join(SAMPLES, "buggy_example.py"),
            engine="watson",
            render=False,
        )


def test_gemini_without_key_rejected():
    env = {k: v for k, v in os.environ.items()
           if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
    old = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        with pytest.raises(ReviewerError, match="GEMINI_API_KEY"):
            pipeline.run_review(
                os.path.join(SAMPLES, "buggy_example.py"),
                engine="gemini",
                render=False,
            )
    finally:
        os.environ.clear()
        os.environ.update(old)
