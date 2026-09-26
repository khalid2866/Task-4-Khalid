"""Tests for Phase 2 — context orchestration."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import ingestion, orchestration
from reviewer.exceptions import OrchestrationError

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _ingest(name: str):
    return ingestion.ingest(os.path.join(SAMPLES, name))


def test_system_instruction_locks_persona():
    si = orchestration.SYSTEM_INSTRUCTION
    assert "Senior Code Quality Assurance Engineer" in si
    assert "Do not write friendly greetings" in si
    assert "only output valid code blocks and direct bullet points" in si


def test_review_context_embeds_fenced_payload():
    ctx = orchestration.build_context(_ingest("buggy_example.py"), mode="review")
    assert "## BUG_REPORT" in ctx.user
    assert "## REFACTORED_CODE" in ctx.user
    assert "```python" in ctx.user
    assert ctx.system == orchestration.SYSTEM_INSTRUCTION
    assert ctx.payload.raw_text in ctx.user  # payload merged, not stripped


def test_explain_context_uses_explain_directive():
    ctx = orchestration.build_context(_ingest("buggy_example.py"), mode="explain")
    assert "## EXPLANATION" in ctx.user
    assert "plain language" in ctx.user


def test_unknown_mode_rejected():
    with pytest.raises(OrchestrationError, match="Unknown mode"):
        orchestration.build_context(_ingest("buggy_example.py"), mode="audit")


def test_semantic_parse_extracts_structure():
    ctx = orchestration.build_context(_ingest("buggy_example.py"), mode="review")
    sem = ctx.semantics
    assert "calculate_total" in sem.functions
    assert "fetch_user" in sem.functions
    assert "os" in sem.imports
    assert sem.syntax_error is None


def test_semantic_parse_reports_syntax_error(tmp_path):
    p = tmp_path / "broken.py"
    p.write_text("def f(:\n    pass\n")
    payload = ingestion.ingest(str(p))
    sem = orchestration.parse_semantics(payload)
    assert sem.syntax_error is not None
    assert "line" in sem.syntax_error


def test_semantic_parse_non_python_heuristic():
    ctx = orchestration.build_context(_ingest("buggy_example.js"), mode="review")
    assert ctx.language == "javascript"
    assert "loadConfig" in ctx.semantics.functions or "greet" in ctx.semantics.functions
