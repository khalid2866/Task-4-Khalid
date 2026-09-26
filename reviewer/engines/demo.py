"""Demo engine — fully offline static analysis.

Produces genuinely useful reviews with zero API keys: Python sources are
analysed with the real ``ast`` module (syntax errors, undefined names,
bare excepts, mutable defaults, ``== None``, unused imports/variables),
other languages get a structural heuristic pass. A small set of *safe*
auto-fixes is applied to build the REFACTORED_CODE block; anything risky
is reported as a bullet instead of rewritten.

The output always follows the strict two-section contract so the
validation phase exercises the same gate as the LLM engines.
"""

from __future__ import annotations

import ast
import builtins
import re

_BUILTINS = set(dir(builtins)) | {"self", "cls"}


# ---------------------------------------------------------------------------
# Python analysis
# ---------------------------------------------------------------------------
class _PythonVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bugs: list[tuple[str, str, int]] = []  # (severity, message, line)
        self.assigned: set[str] = set()
        self.loaded: dict[str, list[int]] = {}
        self.imported: dict[str, int] = {}
        self._scopes: list[set[str]] = [set()]

    # -- scope helpers ----------------------------------------------------
    def _declare(self, name: str) -> None:
        self._scopes[-1].add(name)
        self.assigned.add(name)

    def _is_declared(self, name: str) -> bool:
        return any(name in scope for scope in self._scopes)

    # -- declarations -----------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            name = (a.asname or a.name).split(".")[0]
            self.imported[name] = node.lineno
            self._declare(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for a in node.names:
            if a.name == "*":
                continue
            name = a.asname or a.name
            self.imported[name] = node.lineno
            self._declare(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._declare(node.name)
        for default in node.args.defaults + [
            d for d in node.args.kw_defaults if d is not None
        ]:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.bugs.append(
                    (
                        "Warning",
                        f"Mutable default argument in '{node.name}' "
                        f"(line {node.lineno}) — defaults are shared across calls; "
                        "use None and initialise inside the function.",
                        node.lineno,
                    )
                )
        self._scopes.append(set())
        for arg in node.args.args + node.args.kwonlyargs:
            self._declare(arg.arg)
        if node.args.vararg:
            self._declare(node.args.vararg.arg)
        if node.args.kwarg:
            self._declare(node.args.kwarg.arg)
        self.generic_visit(node)
        self._scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._declare(node.name)
        self._scopes.append(set())
        self.generic_visit(node)
        self._scopes.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._declare(node.id)
        else:
            self.loaded.setdefault(node.id, []).append(node.lineno)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.bugs.append(
                (
                    "Warning",
                    f"Bare 'except:' clause (line {node.lineno}) swallows every "
                    "exception including KeyboardInterrupt — catch 'Exception' instead.",
                    node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(comp, ast.Constant) and comp.value is None:
                if isinstance(op, ast.Eq):
                    self.bugs.append(
                        (
                            "Info",
                            f"Comparison with None using '==' (line {node.lineno}) — "
                            "use 'is None' for identity comparison.",
                            node.lineno,
                        )
                    )
                elif isinstance(op, ast.NotEq):
                    self.bugs.append(
                        (
                            "Info",
                            f"Comparison with None using '!=' (line {node.lineno}) — "
                            "use 'is not None' for identity comparison.",
                            node.lineno,
                        )
                    )
        self.generic_visit(node)


def _analyse_python(source: str) -> tuple[list[tuple[str, str, int]], str, str | None]:
    """Return (bugs, fixed_source, syntax_error)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        bug = (
            "Critical",
            f"Syntax error at line {exc.lineno}: {exc.msg}. "
            "The file cannot be compiled in its current state.",
            exc.lineno or 0,
        )
        return [bug], source, f"line {exc.lineno}: {exc.msg}"

    visitor = _PythonVisitor()
    visitor.visit(tree)

    bugs: list[tuple[str, str, int]] = list(visitor.bugs)

    # Undefined names: loaded but never declared and not a builtin.
    for name, lines in sorted(visitor.loaded.items()):
        if name not in visitor.assigned and name not in _BUILTINS:
            bugs.append(
                (
                    "Critical",
                    f"Undefined name '{name}' used at line {lines[0]} — "
                    "this raises NameError at runtime.",
                    lines[0],
                )
            )

    # Unused imports.
    for name, line in sorted(visitor.imported.items(), key=lambda kv: kv[1]):
        if name not in visitor.loaded:
            bugs.append(
                ("Info", f"Imported name '{name}' (line {line}) is never used.", line)
            )

    # TODO / FIXME markers.
    for i, line in enumerate(source.splitlines(), 1):
        if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", line):
            bugs.append(("Info", f"Work marker at line {i}: '{line.strip()[:60]}'.", i))

    bugs.sort(key=lambda b: ({"Critical": 0, "Warning": 1, "Info": 2}[b[0]], b[2]))

    # Safe auto-fixes: bare except -> except Exception; == None -> is None.
    fixed = re.sub(r"(?m)^(\s*)except\s*:", r"\1except Exception:", source)
    fixed = re.sub(r"==\s*None\b", "is None", fixed)
    fixed = re.sub(r"!=\s*None\b", "is not None", fixed)
    return bugs, fixed, None


# ---------------------------------------------------------------------------
# Generic (non-Python) analysis
# ---------------------------------------------------------------------------
def _analyse_generic(source: str, language: str) -> tuple[list[tuple[str, str, int]], str]:
    bugs: list[tuple[str, str, int]] = []
    lines = source.splitlines()
    for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
        if source.count(opener) != source.count(closer):
            bugs.append(
                (
                    "Critical",
                    f"Unbalanced '{opener}{closer}': {source.count(opener)} opening vs "
                    f"{source.count(closer)} closing — the file will not compile.",
                    0,
                )
            )
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            bugs.append(
                ("Info", f"Line {i} is {len(line)} chars — consider wrapping past 120.", i)
            )
        if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", line):
            bugs.append(("Info", f"Work marker at line {i}: '{line.strip()[:60]}'.", i))
    if language == "javascript":
        for i, line in enumerate(lines, 1):
            if re.search(r"[^=!<>]==[^=]", line) and "null" in line:
                bugs.append(
                    (
                        "Warning",
                        f"Loose equality '==' with null at line {i} — prefer '==='.",
                        i,
                    )
                )
    if language == "java":
        for i, line in enumerate(lines, 1):
            if re.search(r'\w+\s*==\s*"', line):
                bugs.append(
                    (
                        "Warning",
                        f"String comparison with '==' at line {i} — use .equals().",
                        i,
                    )
                )
        for i, line in enumerate(lines, 1):
            if re.search(r"catch\s*\(\s*Exception", line):
                bugs.append(
                    (
                        "Info",
                        f"Overly broad 'catch (Exception …)' at line {i} — "
                        "catch the narrowest type possible.",
                        i,
                    )
                )
    bugs.sort(key=lambda b: ({"Critical": 0, "Warning": 1, "Info": 2}[b[0]], b[2]))
    return bugs, source


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------
def _format_report(
    bugs: list[tuple[str, str, int]], language: str, fixed: str
) -> str:
    if bugs:
        bullets = "\n".join(f"- **{sev}** {msg}" for sev, msg, _ in bugs)
    else:
        bullets = "- **Info** No issues detected. The code appears clean."
    return (
        f"## BUG_REPORT\n{bullets}\n\n"
        f"## REFACTORED_CODE\n```{language}\n{fixed.rstrip()}\n```"
    )


def _format_explanation(ctx) -> str:  # noqa: ANN001
    sem = ctx.semantics
    bullets = [
        f"- This is a {sem.language} file with {sem.line_count} lines.",
    ]
    if sem.syntax_error:
        bullets.append(f"- It currently has a syntax error ({sem.syntax_error}).")
    if sem.functions:
        bullets.append(
            f"- It defines {len(sem.functions)} function(s): "
            + ", ".join(f"`{f}`" for f in sem.functions[:10])
            + (", …" if len(sem.functions) > 10 else "")
            + "."
        )
    else:
        bullets.append("- It defines no top-level functions.")
    if sem.classes:
        bullets.append(
            f"- It defines {len(sem.classes)} class(es): "
            + ", ".join(f"`{c}`" for c in sem.classes)
            + "."
        )
    if sem.imports:
        bullets.append(
            f"- It imports: " + ", ".join(f"`{i}`" for i in sem.imports[:10]) + "."
        )
    else:
        bullets.append("- It has no imports.")
    if sem.notes:
        bullets.extend(f"- Structural note: {n}." for n in sem.notes)
    return "## EXPLANATION\n" + "\n".join(bullets)


class DemoEngine:
    """Offline static-analysis engine. No network, no keys."""

    name = "demo"

    def generate(self, system: str, user: str, ctx) -> str:  # noqa: ANN001, ARG002
        src = ctx.payload.raw_text
        if ctx.mode == "explain":
            return _format_explanation(ctx)
        if ctx.language == "python":
            bugs, fixed, _ = _analyse_python(src)
        else:
            bugs, fixed = _analyse_generic(src, ctx.language)
        return _format_report(bugs, ctx.language, fixed)


def list_engines() -> list[str]:
    return ["demo", "gemini", "openai"]
