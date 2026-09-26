"""Web UI for the Intelligent Code Reviewer & Explainer."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

from reviewer import ingestion, orchestration, validation  # noqa: E402
from reviewer.engines.demo import DemoEngine  # noqa: E402
from reviewer.engines.gemini import GeminiEngine  # noqa: E402
from reviewer.engines.openai import OpenAIEngine  # noqa: E402
from reviewer.exceptions import ReviewerError  # noqa: E402
from reviewer.rendering import markdown_to_html  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def _engine(name: str):
    return {"demo": DemoEngine, "gemini": GeminiEngine, "openai": OpenAIEngine}[name]()


@app.route("/")
def index():
    return render_template(
        "index.html",
        languages=sorted(ingestion.SUPPORTED_EXTENSIONS.items()),
    )


@app.route("/api/review", methods=["POST"])
def api_review():
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip("\n")
    filename = (data.get("filename") or "snippet.py").strip() or "snippet.py"
    engine_name = data.get("engine", "demo")
    mode = data.get("mode", "review")
    if not code:
        return jsonify({"ok": False, "error": "No code supplied."}), 400
    if engine_name not in ("demo", "gemini", "openai"):
        return jsonify({"ok": False, "error": "Unknown engine."}), 400
    if mode not in ("review", "explain"):
        return jsonify({"ok": False, "error": "Unknown mode."}), 400

    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in ingestion.SUPPORTED_EXTENSIONS:
        suffix = ".py"
    tmp = tempfile.NamedTemporaryFile(
        "w", suffix=suffix, delete=False, encoding="utf-8"
    )
    try:
        tmp.write(code)
        tmp.close()
        payload = ingestion.ingest(tmp.name)
        context = orchestration.build_context(payload, mode=mode)
        raw = _engine(engine_name).generate(context.system, context.user, context)
        if mode == "review":
            validated = validation.validate_review(raw, payload.language)
            summary = {
                "bugs": len(validated.bug_bullets),
                "language": validated.code_language,
            }
        else:
            validated = validation.validate_explanation(raw)
            summary = {"bullets": len(validated.bullets)}
    except ReviewerError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"Engine failure: {exc}"}), 502
    finally:
        os.unlink(tmp.name)

    return jsonify(
        {
            "ok": True,
            "html": markdown_to_html(raw),
            "markdown": raw,
            "summary": summary,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5054, debug=False)
