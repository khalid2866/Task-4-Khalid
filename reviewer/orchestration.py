"""Phase 2 — Context Orchestration.

Merges the raw payload with the Persona Constraints (strict system
instructions defined at client initialisation) and performs semantic
parsing: the input string is parsed against the language grammar so the
engine reasons over an abstract model of the program's execution flow
instead of raw text — this is what lets it spot runtime edge cases,
logic gaps and structural smells that regex linters miss.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .exceptions import OrchestrationError
from .ingestion import IngestedFile

# ---------------------------------------------------------------------------
# Persona Constraints — defined once at client initialisation and hardcoded
# into the execution environment (The LLM Taming Matrix, p.11).
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """\
You are a cold, analytical Senior Code Quality Assurance Engineer.

You only output valid code blocks and direct bullet points.

Do not write friendly greetings.\
"""

REVIEW_DIRECTIVE = """\
You must respond with EXACTLY these two sections, in this order, and nothing else:

## BUG_REPORT
- One direct, concise bullet per issue found: syntax anomalies, logical
  vulnerabilities, and performance bugs. Prefix critical issues with **Critical**,
  warnings with **Warning**, informational notes with **Info**.

## REFACTORED_CODE
A single Markdown-fenced code block containing the corrected, compilable code.

Rules:
- No greetings, no introductions, no closing remarks.
- No prose outside the two sections.
- The REFACTORED_CODE fence must use the correct language tag."""

EXPLAIN_DIRECTIVE = """\
You must respond with EXACTLY this section and nothing else:

## EXPLANATION
- Direct, concise bullet points explaining in plain language what the code
  does, how its main parts work together, and any notable behaviour.

Rules:
- No greetings, no introductions, no closing remarks.
- No code blocks; explain in plain language only."""


@dataclass
class SemanticModel:
    """Abstract model of the program's execution flow."""

    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    line_count: int = 0
    syntax_error: str | None = None
    notes: list[str] = field(default_factory=list)


def parse_semantics(payload: IngestedFile) -> SemanticModel:
    """Build the abstract execution-flow model for the payload.

    Python sources get a true AST parse (Module -> FunctionDef/ClassDef/
    Import nodes). Other languages get a structural heuristic pass.
    """
    model = SemanticModel(language=payload.language, line_count=payload.line_count)
    src = payload.raw_text

    if payload.language == "python":
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            model.syntax_error = f"line {exc.lineno}: {exc.msg}"
            return model
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                model.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                model.classes.append(node.name)
            elif isinstance(node, ast.Import):
                model.imports.extend(a.asname or a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                model.imports.extend(a.asname or a.name for a in node.names)
        return model

    # Heuristic structural pass for non-Python languages.
    _KEYWORDS = {
        "if", "for", "while", "catch", "switch", "return", "synchronized",
        "function", "def", "class",
    }
    matches = re.findall(r"(?:function\s+(\w+)|(\w+)\s*\([^)]*\)\s*\{)", src)
    model.functions = sorted(
        {name for tup in matches for name in tup if name and name not in _KEYWORDS}
    )
    model.imports = sorted(
        set(re.findall(r"^\s*(?:import|#include|require)\s+[\"'<]?([\w./-]+)", src, re.M))
    )
    for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
        if src.count(opener) != src.count(closer):
            model.notes.append(
                f"Unbalanced '{opener}{closer}': {src.count(opener)} vs {src.count(closer)}"
            )
    return model


@dataclass
class ReviewContext:
    """The fully assembled payload handed to the API client."""

    system: str
    user: str
    language: str
    mode: str
    semantics: SemanticModel
    payload: IngestedFile


def build_context(payload: IngestedFile, mode: str = "review") -> ReviewContext:
    """Merge payload + persona constraints into the engine-ready context."""
    if mode not in ("review", "explain"):
        raise OrchestrationError(
            f"Unknown mode '{mode}'. Expected 'review' or 'explain'."
        )
    try:
        semantics = parse_semantics(payload)
    except Exception as exc:  # semantic parsing must never crash the pipeline
        raise OrchestrationError(f"Semantic parsing failed: {exc}") from None

    directive = REVIEW_DIRECTIVE if mode == "review" else EXPLAIN_DIRECTIVE
    fenced = f"```{payload.language}\n{payload.raw_text}\n```"
    user = (
        f"{directive}\n\n"
        f"Language: {payload.language} | Lines: {payload.line_count}\n"
        f"Structural summary: {len(semantics.functions)} function(s), "
        f"{len(semantics.classes)} class(es), {len(semantics.imports)} import(s)."
        + (f" Syntax error present: {semantics.syntax_error}." if semantics.syntax_error else "")
        + f"\n\nReview the following code:\n\n{fenced}"
    )
    return ReviewContext(
        system=SYSTEM_INSTRUCTION,
        user=user,
        language=payload.language,
        mode=mode,
        semantics=semantics,
        payload=payload,
    )
