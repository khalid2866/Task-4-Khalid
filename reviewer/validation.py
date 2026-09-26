"""Phase 3 — Structured Output Validation.

The script verifies the exact presence of ``## BUG_REPORT`` and
``## REFACTORED_CODE``. If the engine fails to return both explicit
section headers, the response is rejected so malformed reports are
never pushed down the pipeline.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from .exceptions import ValidationError

BUG_HEADER = "## BUG_REPORT"
FIX_HEADER = "## REFACTORED_CODE"
EXPLAIN_HEADER = "## EXPLANATION"

# Conversational filler that the taming matrix explicitly forbids.
_FILLER_PATTERNS = (
    r"^sure[,.]",
    r"^of course[,.]",
    r"^certainly[,.]",
    r"^here(?:'s| is) your",
    r"^happy to help",
    r"^as an ai",
)


def _section_spans(text: str) -> dict[str, tuple[int, int]]:
    """Map each ## HEADER to its (start, end) character span."""
    matches = list(re.finditer(r"(?m)^##\s+([A-Z_]+)\s*$", text))
    spans: dict[str, tuple[int, int]] = {}
    for i, m in enumerate(matches):
        header = "## " + m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans[header] = (m.end(), end)
    return spans


def _reject_filler(text: str) -> None:
    head = text.lstrip()[:120].lower()
    for pattern in _FILLER_PATTERNS:
        if re.match(pattern, head):
            raise ValidationError(
                "Response rejected: conversational filler detected "
                f"(matched '{pattern}'). The persona requires direct output only."
            )


@dataclass
class ValidatedReport:
    bug_bullets: list[str]
    refactored_code: str
    code_language: str
    raw: str


@dataclass
class ValidatedExplanation:
    bullets: list[str]
    raw: str


def validate_review(text: str, language: str) -> ValidatedReport:
    """Validate a review-mode response. Raises ValidationError on any fault."""
    if not text or not text.strip():
        raise ValidationError("Response rejected: empty response from engine.")
    _reject_filler(text)

    spans = _section_spans(text)
    for header in (BUG_HEADER, FIX_HEADER):
        if header not in spans:
            raise ValidationError(
                f"Response rejected: missing required section '{header}'. "
                "Malformed reports are never pushed to the pipeline."
            )
    if list(spans).index(BUG_HEADER) > list(spans).index(FIX_HEADER):
        raise ValidationError(
            "Response rejected: '## BUG_REPORT' must come before '## REFACTORED_CODE'."
        )

    # BUG_REPORT must contain only direct, concise bullet points.
    bug_body = text[spans[BUG_HEADER][0] : spans[BUG_HEADER][1]]
    bullets = [
        ln.strip()
        for ln in bug_body.splitlines()
        if ln.strip() and not ln.strip().startswith("```")
    ]
    if not bullets:
        raise ValidationError("Response rejected: '## BUG_REPORT' has no content.")
    non_bullets = [ln for ln in bullets if not re.match(r"^[-*]\s+", ln)]
    if non_bullets:
        raise ValidationError(
            "Response rejected: '## BUG_REPORT' must contain only bullet points; "
            f"found prose: '{non_bullets[0][:60]}…'"
        )

    # REFACTORED_CODE must contain exactly one valid fenced code block.
    fix_body = text[spans[FIX_HEADER][0] : spans[FIX_HEADER][1]]
    fences = re.findall(r"```(\w*)\n(.*?)```", fix_body, re.S)
    if len(fences) != 1:
        raise ValidationError(
            "Response rejected: '## REFACTORED_CODE' must contain exactly one "
            f"Markdown-fenced code block (found {len(fences)})."
        )
    fence_lang, code = fences[0]
    if not code.strip():
        raise ValidationError("Response rejected: fenced code block is empty.")

    # The refactored code must be compilable (Python check via ast/compile).
    if language == "python" or fence_lang == "python":
        try:
            compile(code, "<refactored>", "exec")
        except SyntaxError as exc:
            raise ValidationError(
                f"Response rejected: refactored code does not compile "
                f"(line {exc.lineno}: {exc.msg})."
            ) from None
    # Reject any *additional* unknown sections (structural noise).
    known = {BUG_HEADER, FIX_HEADER}
    unknown = [h for h in spans if h not in known]
    if unknown:
        raise ValidationError(
            f"Response rejected: unexpected section(s) {unknown} — "
            "only BUG_REPORT and REFACTORED_CODE are allowed."
        )

    return ValidatedReport(
        bug_bullets=bullets,
        refactored_code=code.rstrip() + "\n",
        code_language=fence_lang or language,
        raw=text,
    )


def validate_explanation(text: str) -> ValidatedExplanation:
    """Validate an explain-mode response."""
    if not text or not text.strip():
        raise ValidationError("Response rejected: empty response from engine.")
    _reject_filler(text)
    spans = _section_spans(text)
    if EXPLAIN_HEADER not in spans:
        raise ValidationError(
            "Response rejected: missing required section '## EXPLANATION'."
        )
    body = text[spans[EXPLAIN_HEADER][0] : spans[EXPLAIN_HEADER][1]]
    bullets = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not bullets or not all(re.match(r"^[-*]\s+", ln) for ln in bullets):
        raise ValidationError(
            "Response rejected: '## EXPLANATION' must contain only bullet points."
        )
    return ValidatedExplanation(bullets=bullets, raw=text)
