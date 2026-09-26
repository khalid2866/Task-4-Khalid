"""Tests for the offline demo engine."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import ingestion, orchestration, validation
from reviewer.engines.demo import DemoEngine, list_engines

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _review(name: str, mode: str = "review") -> str:
    payload = ingestion.ingest(os.path.join(SAMPLES, name))
    ctx = orchestration.build_context(payload, mode=mode)
    return DemoEngine().generate(ctx.system, ctx.user, ctx)


def test_lists_available_engines():
    assert set(list_engines()) == {"demo", "gemini", "openai"}


def test_python_report_has_both_headers_and_validates():
    raw = _review("buggy_example.py")
    assert "## BUG_REPORT" in raw and "## REFACTORED_CODE" in raw
    validation.validate_review(raw, "python")  # must pass the real gate


def test_detects_undefined_names():
    raw = _review("buggy_example.py")
    assert "db" in raw and "transform" in raw


def test_detects_bare_except_and_mutable_default():
    raw = _review("buggy_example.py")
    assert "Bare 'except:'" in raw
    assert "Mutable default argument" in raw


def test_detects_none_comparison_and_applies_fix():
    raw = _review("buggy_example.py")
    assert "is None" in raw  # fixed code uses identity comparison


def test_syntax_error_reported_not_crashed(tmp_path):
    p = tmp_path / "broken.py"
    p.write_text("def f(:\n    pass\n")
    payload = ingestion.ingest(str(p))
    ctx = orchestration.build_context(payload, mode="review")
    raw = DemoEngine().generate(ctx.system, ctx.user, ctx)
    assert "**Critical**" in raw and "Syntax error" in raw
    # A syntax-broken file cannot be refactored; the gate checks structure only.
    assert "## BUG_REPORT" in raw and "## REFACTORED_CODE" in raw


def test_js_analysis_flags_loose_null_check():
    raw = _review("buggy_example.js")
    assert "## BUG_REPORT" in raw
    assert "===" in raw  # suggests strict equality


def test_java_analysis_flags_string_equality():
    raw = _review("buggy_example.java")
    assert "## BUG_REPORT" in raw
    assert ".equals()" in raw


def test_clean_code_reports_no_issues(tmp_path):
    p = tmp_path / "clean.py"
    p.write_text("def add(a, b):\n    return a + b\n")
    payload = ingestion.ingest(str(p))
    ctx = orchestration.build_context(payload, mode="review")
    raw = DemoEngine().generate(ctx.system, ctx.user, ctx)
    assert "No issues detected" in raw
    validation.validate_review(raw, "python")


def test_explain_mode_produces_plain_bullets():
    raw = _review("buggy_example.py", mode="explain")
    assert raw.startswith("## EXPLANATION")
    assert "```" not in raw  # plain language only, no code blocks
    validation.validate_explanation(raw)
