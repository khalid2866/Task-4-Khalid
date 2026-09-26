"""Tests for Phase 3 — structured output validation gate."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import validation
from reviewer.exceptions import ValidationError

VALID = """## BUG_REPORT
- **Critical** Undefined name 'db' used at line 5 — this raises NameError at runtime.
- **Warning** Bare 'except:' clause (line 8) swallows every exception.

## REFACTORED_CODE
```python
def fetch_user(user_id):
    return None
```
"""


def test_valid_report_passes():
    v = validation.validate_review(VALID, "python")
    assert len(v.bug_bullets) == 2
    assert "def fetch_user" in v.refactored_code
    assert v.code_language == "python"


def test_missing_bug_header_rejected():
    bad = VALID.replace("## BUG_REPORT", "## BUGS")
    with pytest.raises(ValidationError, match="BUG_REPORT"):
        validation.validate_review(bad, "python")


def test_missing_fix_header_rejected():
    bad = VALID.split("## REFACTORED_CODE")[0]
    with pytest.raises(ValidationError, match="REFACTORED_CODE"):
        validation.validate_review(bad, "python")


def test_wrong_section_order_rejected():
    bad = VALID.replace("## BUG_REPORT", "## TMP").replace(
        "## REFACTORED_CODE", "## BUG_REPORT"
    ).replace("## TMP", "## REFACTORED_CODE")
    with pytest.raises(ValidationError, match="must come before"):
        validation.validate_review(bad, "python")


def test_prose_in_bug_report_rejected():
    bad = VALID.replace(
        "- **Critical** Undefined",
        "Here is what I found:\n- **Critical** Undefined",
    )
    with pytest.raises(ValidationError, match="only bullet points"):
        validation.validate_review(bad, "python")


def test_multiple_fences_rejected():
    bad = VALID + "\n```python\nx = 1\n```\n"
    with pytest.raises(ValidationError, match="exactly one"):
        validation.validate_review(bad, "python")


def test_uncompilable_refactored_rejected():
    bad = VALID.replace(
        "def fetch_user(user_id):\n    return None",
        "def fetch_user(user_id:(\n    return None",
    )
    with pytest.raises(ValidationError, match="does not compile"):
        validation.validate_review(bad, "python")


def test_conversational_filler_rejected():
    bad = "Sure, here is your code!\n" + VALID
    with pytest.raises(ValidationError, match="conversational filler"):
        validation.validate_review(bad, "python")


def test_unknown_section_rejected():
    bad = VALID + "\n## EXTRA_NOTES\n- hi\n"
    with pytest.raises(ValidationError, match="unexpected section"):
        validation.validate_review(bad, "python")


def test_empty_response_rejected():
    with pytest.raises(ValidationError, match="empty"):
        validation.validate_review("   \n", "python")


def test_explain_validation():
    good = "## EXPLANATION\n- This file defines two functions.\n- It has no imports.\n"
    v = validation.validate_explanation(good)
    assert len(v.bullets) == 2
    with pytest.raises(ValidationError, match="EXPLANATION"):
        validation.validate_explanation("- no header here\n")
