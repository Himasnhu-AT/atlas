"""
Static analysis for a student's Python project.

Reads a file or directory path as argv[1], walks it, and prints one JSON object
on stdout. Standard library only, because this runs inside somebody else's
repository and installing into it would be rude and often impossible.

What it checks, in rough order of how often it catches something real:

  syntax          the file does not parse, with the exact line and column
  undefined-name  a name is used that is never defined, imported, or built in
  stub            NotImplementedError or a bare `pass` body left in a function
  unused-import   an import nothing in the file refers to
  bare-except     `except:` swallowing everything, including KeyboardInterrupt
  mutable-default a mutable value used as a default argument

What it deliberately does not do: type inference, cross-module resolution, or
anything requiring a third-party analyser. Those need either a heavyweight tool
or a lot of wrong answers, and a checker that cries wolf gets switched off.
"""

from __future__ import annotations

import ast
import builtins
import json
import os
import sys

BUILTINS = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__", "__spec__"}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "target", "dist", "build", ".next", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", "site-packages",
}

MAX_FILES = 400


def diagnostic(file, line, column, severity, message, rule):
    return {
        "file": file,
        "line": max(int(line or 1), 1),
        "column": max(int(column or 0), 0),
        "severity": severity,
        "message": message,
        "rule": rule,
    }


class Collector(ast.NodeVisitor):
    """
    Gathers every name a module defines and every name it uses.

    Scope handling is deliberately flat: a real scope analysis needs to model
    comprehensions, closures, globals and class bodies correctly, and getting it
    subtly wrong produces confident false positives. Treating the module as one
    namespace under-reports, which is the right direction to be wrong in.
    """

    def __init__(self):
        self.defined: set[str] = set()
        self.used: list[tuple[str, int, int]] = []
        self.imports: dict[str, tuple[int, int]] = {}

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.defined.add(name)
            self.imports[name] = (node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == "*":
                # A star import can define anything, so undefined-name checking
                # would be guesswork from here on.
                self.defined.add("*")
                continue
            name = alias.asname or alias.name
            self.defined.add(name)
            self.imports[name] = (node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.defined.add(node.name)
        self._bind_arguments(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self._bind_arguments(node)
        self.generic_visit(node)

    def _bind_arguments(self, node):
        args = node.args
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            for arg in group:
                self.defined.add(arg.arg)
        if args.vararg:
            self.defined.add(args.vararg.arg)
        if args.kwarg:
            self.defined.add(args.kwarg.arg)

    def visit_ClassDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.defined.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.used.append((node.id, node.lineno, node.col_offset))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.defined.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node):
        self.defined.update(node.names)
        self.generic_visit(node)

    visit_Nonlocal = visit_Global


def check_module(path: str, rel: str) -> list[dict]:
    try:
        source = open(path, encoding="utf8").read()
    except (OSError, UnicodeDecodeError) as error:
        return [diagnostic(rel, 1, 0, "warning", f"could not read this file: {error}", "unreadable")]

    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as error:
        return [
            diagnostic(
                rel,
                error.lineno,
                error.offset,
                "error",
                error.msg or "invalid syntax",
                "syntax",
            )
        ]

    found: list[dict] = []
    collector = Collector()
    collector.visit(tree)

    if "*" not in collector.defined:
        seen: set[str] = set()
        for name, line, column in collector.used:
            if name in collector.defined or name in BUILTINS or name in seen:
                continue
            seen.add(name)
            found.append(
                diagnostic(
                    rel, line, column, "error",
                    f"`{name}` is used here but never defined or imported",
                    "undefined-name",
                )
            )

    used_names = {name for name, _, _ in collector.used}
    for name, (line, column) in sorted(collector.imports.items(), key=lambda kv: kv[1]):
        if name not in used_names and name not in ("annotations",):
            found.append(
                diagnostic(
                    rel, line, column, "warning",
                    f"`{name}` is imported but never used",
                    "unused-import",
                )
            )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.extend(_check_function(node, rel))
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            found.append(
                diagnostic(
                    rel, node.lineno, node.col_offset, "warning",
                    "`except:` catches everything, including Ctrl-C and SystemExit. "
                    "Catch the exceptions you can actually handle.",
                    "bare-except",
                )
            )

    return found


def _check_function(node, rel: str) -> list[dict]:
    found = []

    body = [stmt for stmt in node.body if not _is_docstring(stmt)]

    raises_not_implemented = any(
        isinstance(stmt, ast.Raise)
        and isinstance(stmt.exc, (ast.Name, ast.Call))
        and _raised_name(stmt.exc) == "NotImplementedError"
        for stmt in body
    )
    only_pass = len(body) == 1 and isinstance(body[0], ast.Pass)

    if raises_not_implemented or only_pass:
        found.append(
            diagnostic(
                rel, node.lineno, node.col_offset, "warning",
                f"`{node.name}` is still a stub",
                "stub",
            )
        )

    for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            found.append(
                diagnostic(
                    rel, default.lineno, default.col_offset, "warning",
                    f"`{node.name}` has a mutable default argument, which is created once "
                    "and shared by every call",
                    "mutable-default",
                )
            )

    return found


def _raised_name(exc):
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
        return exc.func.id
    return None


def _is_docstring(stmt):
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(
        stmt.value.value, str
    )


def collect_files(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target] if target.endswith(".py") else []

    files = []
    for directory, subdirs, names in os.walk(target):
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(names):
            if name.endswith(".py"):
                files.append(os.path.join(directory, name))
                if len(files) >= MAX_FILES:
                    return files
    return files


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"files_checked": 0, "diagnostics": []}))
        return 0

    target = sys.argv[1]
    root = os.getcwd()

    diagnostics = []
    files = collect_files(target)

    for path in files:
        rel = os.path.relpath(path, root)
        diagnostics.extend(check_module(path, rel))

    # Errors first, then by location, so the list reads in the order a person
    # would want to fix things.
    severity_rank = {"error": 0, "warning": 1}
    diagnostics.sort(key=lambda d: (severity_rank.get(d["severity"], 2), d["file"], d["line"]))

    print(json.dumps({"files_checked": len(files), "diagnostics": diagnostics}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
