# 🛡️ Intelligent Code Reviewer & Explainer

**Generative AI Project 4** — an autonomous, AI-powered code gatekeeper.
Point it at any source file and it returns a strict, machine-checkable review:
a `## BUG_REPORT` of syntax anomalies, logical vulnerabilities and performance
bugs, plus a `## REFACTORED_CODE` block — rendered in your terminal with
IDE-quality syntax highlighting.

Built exactly to the *Project 4: Intelligent Code Reviewer & Explainer*
blueprint (DecodeLabs Industrial Training Kit):

| Blueprint phase | This project |
|---|---|
| 1. Ingest Payload | `reviewer/ingestion.py` — raw file → string buffer, whitespace preserved byte-for-byte, triage for missing / locked / badly-encoded files |
| 2. Context Orchestration | `reviewer/orchestration.py` — AST semantic parsing + strict persona system instructions |
| 3. Structured Output Validation | `reviewer/validation.py` — rejects any response missing `## BUG_REPORT` / `## REFACTORED_CODE` |
| 4. Terminal Rendering | `reviewer/rendering.py` — `rich.markdown` color-mapped syntax highlighting |

## Quick start (5 minutes)

**1. Install Python 3.10+**, then:

```bash
cd code-reviewer-studio
pip install -r requirements.txt
```

**2. Run your first review** (no API key needed — the offline engine):

```bash
python -m reviewer review samples/buggy_example.py
```

You get a `## BUG_REPORT` with severity-tagged bullets and a
`## REFACTORED_CODE` block, syntax-highlighted right in the terminal.

**3. Try explain mode:**

```bash
python -m reviewer explain samples/buggy_example.java
```

**4. Try the web UI:**

```bash
python web/app.py
# open http://127.0.0.1:5054
```

Paste code or drop a file in, pick an engine, and get a highlighted report.

## CLI reference

```bash
python -m reviewer review <file> [--engine demo|gemini|openai] [--plain] [--save]
python -m reviewer explain <file> [--engine demo|gemini|openai] [--plain] [--save]
python -m reviewer engines      # list engines
python -m reviewer languages    # list supported extensions
```

- `--engine demo` (default): fully offline static analysis. No keys, no network.
- `--engine gemini`: Google GenAI API — needs `GEMINI_API_KEY` in `.env`.
- `--engine openai`: OpenAI API — needs `OPENAI_API_KEY` in `.env`.
- `--plain`: print raw markdown instead of Rich highlighted output.
- `--save`: write the report + a `manifest.json` stage log into `./reports/`.

Supported files: `.py .js .ts .java .cpp .c .go .json`

## Using a real LLM (Gemini)

1. Copy `.env.example` to `.env` and add your key:

   ```bash
   cp .env.example .env
   # edit .env -> GEMINI_API_KEY=your-key-here
   ```

   Get a free key at <https://aistudio.google.com/apikey>.

2. Run:

   ```bash
   python -m reviewer review samples/buggy_example.py --engine gemini --save
   ```

The persona constraints are locked at client initialisation
(`reviewer/orchestration.py::SYSTEM_INSTRUCTION`) — the model acts as a cold,
analytical Senior QA Engineer and may only output valid code blocks and direct
bullet points. Any response that breaks the contract (missing headers,
conversational filler, uncompilable refactored code, extra sections) is
rejected by the validation gate before it ever reaches your screen.

## Project layout

```
code-reviewer-studio/
├── reviewer/
│   ├── __main__.py        # CLI (review / explain / engines / languages)
│   ├── pipeline.py        # the 4-stage IPO pipeline + stage log
│   ├── ingestion.py       # Phase 1: raw file -> string buffer + triage
│   ├── orchestration.py   # Phase 2: AST parsing + persona constraints
│   ├── validation.py      # Phase 3: structured-output gate
│   ├── rendering.py       # Phase 4: rich terminal + HTML rendering
│   ├── exceptions.py      # typed errors per phase
│   └── engines/
│       ├── demo.py        # offline static analyser (Python AST + heuristics)
│       ├── gemini.py      # Google GenAI client
│       └── openai.py      # OpenAI client
├── web/
│   ├── app.py             # Flask UI
│   └── templates/index.html
├── samples/               # buggy_example.py / .js / .java for demos
├── tests/                 # 47 pytest tests
├── reports/               # created by --save (git-ignored)
├── requirements.txt
├── .env.example
├── run.sh / run.bat
└── README.md
```

## Running the tests

```bash
python -m pytest tests/ -q
```

47 tests cover ingestion triage (missing/locked/binary/bad-encoding files),
orchestration (persona lock, AST parsing), the validation gate (missing
headers, filler, uncompilable code), the demo engine (real bug detection),
rendering, and the full end-to-end pipeline.

## How the demo engine finds bugs (Python)

- `SyntaxError` via `ast.parse` (with line number)
- Undefined names (NameError at runtime) via scope analysis
- Bare `except:` clauses, mutable default arguments, `== None` / `!= None`
- Unused imports, TODO/FIXME markers

Safe auto-fixes applied to the refactored block: `except:` → `except Exception:`,
`== None` → `is None`, `!= None` → `is not None`. Anything risky is reported
as a bullet instead of rewritten.

## Notes

- Files are read as **untrusted input** and never executed.
- 2 MiB per-file payload cap; binary files are rejected.
- The refactored Python block is compile-checked before it is accepted.
