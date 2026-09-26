"""The Complete IPO Pipeline.

    1. Local System  — open().read() streams the raw file into a string buffer
    2. API Client    — payload merges with the Persona Constraints and enters
                       the engine (Google GenAI / OpenAI / offline demo)
    3. Validation   — script verifies the exact presence of ## BUG_REPORT
                       and ## REFACTORED_CODE
    4. Terminal     — Rich engine compiles the markdown and prints
                       color-coded syntax to standard output
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import ingestion, orchestration, rendering, validation
from .engines.demo import DemoEngine
from .engines.gemini import GeminiEngine
from .engines.openai import OpenAIEngine
from .exceptions import EngineError, ReviewerError

STAGES = (
    "ingest_payload",
    "context_orchestration",
    "ai_review",
    "structured_validation",
    "terminal_render",
)


@dataclass
class StageRecord:
    stage: str
    status: str  # ok | failed | skipped
    seconds: float
    detail: str = ""


@dataclass
class ReviewResult:
    path: str
    language: str
    mode: str
    engine: str
    report: str = ""
    stages: list[StageRecord] = field(default_factory=list)
    validated: object = None
    report_path: str | None = None
    manifest_path: str | None = None
    total_seconds: float = 0.0


def _make_engine(name: str):
    if name == "demo":
        return DemoEngine()
    if name == "gemini":
        return GeminiEngine()
    if name == "openai":
        return OpenAIEngine()
    raise EngineError(
        f"Unknown engine '{name}'. Available: demo, gemini, openai."
    )


def run_review(
    path: str,
    engine: str = "demo",
    mode: str = "review",
    plain: bool = False,
    save_dir: str | None = None,
    render: bool = True,
) -> ReviewResult:
    """Run the full 4-stage pipeline. Raises ReviewerError on any failure."""
    started = time.perf_counter()
    stages: list[StageRecord] = []
    result = ReviewResult(path=path, language="", mode=mode, engine=engine)

    # -- Stage 1: Local System ------------------------------------------------
    t0 = time.perf_counter()
    try:
        payload = ingestion.ingest(path)
    except ReviewerError:
        raise
    result.language = payload.language
    stages.append(
        StageRecord(
            "ingest_payload", "ok", time.perf_counter() - t0,
            f"{payload.size_bytes} bytes, {payload.line_count} lines, "
            f"language={payload.language}, sha256={payload.sha256[:12]}…",
        )
    )

    # -- Stage 2: API Client (context orchestration + engine call) ------------
    t0 = time.perf_counter()
    context = orchestration.build_context(payload, mode=mode)
    engine_obj = _make_engine(engine)
    try:
        raw_report = engine_obj.generate(context.system, context.user, context)
    except ReviewerError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalise engine faults
        raise EngineError(f"Engine '{engine}' failed: {exc}") from None
    result.report = raw_report
    stages.append(
        StageRecord(
            "context_orchestration", "ok", 0.0,
            f"AST parse: {len(context.semantics.functions)} fn / "
            f"{len(context.semantics.classes)} class; persona constraints merged",
        )
    )
    stages.append(
        StageRecord(
            "ai_review", "ok", time.perf_counter() - t0,
            f"engine={engine_obj.name}, chars={len(raw_report)}",
        )
    )

    # -- Stage 3: Validation --------------------------------------------------
    t0 = time.perf_counter()
    if mode == "review":
        result.validated = validation.validate_review(raw_report, payload.language)
        detail = (
            f"headers verified; {len(result.validated.bug_bullets)} bullets; "
            "refactored block compiles"
        )
    else:
        result.validated = validation.validate_explanation(raw_report)
        detail = f"headers verified; {len(result.validated.bullets)} bullets"
    stages.append(
        StageRecord("structured_validation", "ok", time.perf_counter() - t0, detail)
    )

    # -- Stage 4: Terminal ----------------------------------------------------
    t0 = time.perf_counter()
    if render:
        rendering.render_terminal(raw_report, plain=plain)
    stages.append(
        StageRecord(
            "terminal_render", "ok", time.perf_counter() - t0,
            "rich markdown" if not plain else "plain text",
        )
    )

    # -- Persist report + manifest -------------------------------------------
    result.stages = stages
    result.total_seconds = time.perf_counter() - started
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_path = os.path.join(save_dir, f"{stem}-{mode}-{stamp}.md")
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(raw_report if raw_report.endswith("\n") else raw_report + "\n")
        manifest = {
            "path": path,
            "language": payload.language,
            "mode": mode,
            "engine": engine_obj.name,
            "sha256": payload.sha256,
            "report_file": os.path.basename(report_path),
            "stages": [
                {"stage": s.stage, "status": s.status,
                 "seconds": round(s.seconds, 3), "detail": s.detail}
                for s in stages
            ],
            "total_seconds": round(result.total_seconds, 3),
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = os.path.join(save_dir, f"{stem}-{mode}-{stamp}.manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        result.report_path = report_path
        result.manifest_path = manifest_path

    return result
