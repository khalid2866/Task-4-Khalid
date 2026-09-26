"""CLI for the Intelligent Code Reviewer & Explainer.

Usage:
    python -m reviewer review path/to/file.py [--engine demo|gemini|openai]
    python -m reviewer explain path/to/file.js [--engine demo]
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from .exceptions import ReviewerError
from .ingestion import list_supported
from .pipeline import run_review

load_dotenv()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reviewer",
        description="Intelligent Code Reviewer & Explainer — AI-powered code gatekeeper.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    for cmd, help_text in (
        ("review", "Analyse a code file: bug report + refactored code."),
        ("explain", "Explain a code file in plain language."),
    ):
        sp = sub.add_parser(cmd, help=help_text)
        sp.add_argument("path", help="Path to the source file to analyse.")
        sp.add_argument(
            "--engine",
            default="demo",
            choices=["demo", "gemini", "openai"],
            help="Review engine (default: demo — fully offline).",
        )
        sp.add_argument(
            "--plain",
            action="store_true",
            help="Print raw markdown instead of Rich highlighted output.",
        )
        sp.add_argument(
            "--save",
            action="store_true",
            help="Save the report + manifest JSON into ./reports/.",
        )
        sp.add_argument(
            "--reports-dir",
            default="reports",
            help="Directory for --save output (default: reports).",
        )

    sub.add_parser("engines", help="List available review engines.")
    sub.add_parser("languages", help="List supported source file extensions.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "engines":
        print("demo   — offline static analysis (no API key needed)")
        print("gemini — Google GenAI API (needs GEMINI_API_KEY)")
        print("openai — OpenAI API (needs OPENAI_API_KEY)")
        return 0
    if args.command == "languages":
        for ext, lang in sorted(list_supported().items()):
            print(f"{ext:>6}  ->  {lang}")
        return 0

    try:
        result = run_review(
            args.path,
            engine=args.engine,
            mode=args.command,
            plain=args.plain,
            save_dir=args.reports_dir if args.save else None,
        )
    except ReviewerError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    if args.save:
        print(f"\nSaved report:   {result.report_path}")
        print(f"Saved manifest: {result.manifest_path}")
    print(f"\nDone in {result.total_seconds:.2f}s "
          f"({result.engine}/{result.mode}, {result.language}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
