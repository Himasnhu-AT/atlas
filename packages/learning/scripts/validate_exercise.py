"""
Static and dynamic checks for one exercise directory.

`build.ts` already runs the reference solution against the test. That catches a
broken reference and nothing else. This script catches the rest: a scaffold that
passes, a signature that drifted between scaffold and reference, a typo that
would otherwise arrive as a wall of unittest output, an import that would need
pip, and a hang.

Every problem is reported as one line naming the file, the problem, and what
would have been correct. Output is JSON on stdout so the caller parses a result
rather than scraping text:

    {"problems": ["scaffold.py line 12: unexpected indent ..."]}

The exit status is 0 unless the arguments are unusable. A failed check is data,
not a crash. Standard library only, like everything else students run.

Usage:
    python3 validate_exercise.py --dir <exercise-dir> --lib <course-lib-dir>
        [--scaffold scaffold.py] [--reference reference.py] [--test test.py]
        [--timeout 60]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile

# The student's working file. Fixed by design: one test file grades both the
# student's attempt and the reference solution.
SOLUTION_FILENAME = "solution.py"

# `solution` is the student's own file. The rest of what an exercise may import
# comes from its course's lib directory, which the build copies into the
# workspace: the AI course ships `mockllm`, another course ships something else.
# Nothing beyond that, because the platform's promise is that Python 3.10 is the
# only requirement.
BASE_LOCAL_MODULES = frozenset({"solution"})


def local_modules(lib_dir) -> frozenset:
    """Module names a course makes available by copying files into the workspace."""
    if not lib_dir or not os.path.isdir(lib_dir):
        return BASE_LOCAL_MODULES
    names = {
        os.path.splitext(name)[0]
        for name in os.listdir(lib_dir)
        if name.endswith(".py") and not name.startswith(".")
    }
    return BASE_LOCAL_MODULES | names


def copy_lib(lib_dir, dest) -> None:
    """Copy a course's lib files into an exercise workspace."""
    if not lib_dir or not os.path.isdir(lib_dir):
        return
    for name in os.listdir(lib_dir):
        if name == "__pycache__" or name.startswith("."):
            continue
        source = os.path.join(lib_dir, name)
        if os.path.isfile(source):
            shutil.copy(source, os.path.join(dest, name))

# sys.stdlib_module_names is 3.10+, exact, and costs nothing to maintain.
STDLIB = frozenset(sys.stdlib_module_names)


# Reading and parsing


def read_source(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def preflight(name: str, source: str, path: str):
    """
    Parse and compile one file, returning (tree, problem).

    Two passes, because they catch different things. ast.parse() runs only the
    parser, so it happily accepts `await` outside an async function, `return` at
    module level, a duplicated parameter name, and `nonlocal` with nothing to
    bind. Those are SyntaxErrors that only the symbol table and code generation
    pass in compile() raises. Compiling the tree we already have costs a
    millisecond and buys that second class of error.
    """
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        return None, _syntax_problem(name, error)
    try:
        compile(tree, path, "exec")
    except SyntaxError as error:
        return None, _syntax_problem(name, error)
    except ValueError as error:
        return None, f"{name}: {error}"
    return tree, None


def _syntax_problem(name: str, error: SyntaxError) -> str:
    line = getattr(error, "lineno", None) or 0
    column = getattr(error, "offset", None) or 1
    kind = type(error).__name__
    head = f"{name} line {line}, column {column}: {error.msg} ({kind})"
    text = (error.text or "").rstrip("\n")
    if not text:
        return head
    caret = " " * max(column - 1, 0) + "^"
    return f"{head}\n  {text}\n  {caret}"


# Definitions and signatures


def _definitions(tree: ast.Module) -> dict:
    """
    Every name a module makes importable, mapped to the node that binds it.

    Only bindings at module level count, since those are the ones `from solution
    import x` can reach. Bodies of top-level `if` and `try` are included, because
    a conditional definition is still a definition.
    """
    found: dict = {}

    def collect(body) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found.setdefault(node.name, node)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.setdefault(target.id, node)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    found.setdefault(node.target.id, node)
            elif isinstance(node, ast.If):
                collect(node.body)
                collect(node.orelse)
            elif isinstance(node, ast.Try):
                collect(node.body)
                collect(node.orelse)
                collect(node.finalbody)

    collect(tree.body)
    return found


def _kind(node) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "function"
    return "value"


def _signature(fn) -> dict:
    """The parts of a signature a caller can actually see."""
    args = fn.args
    positional = [p.arg for p in args.posonlyargs + args.args]
    defaulted = set(positional[len(positional) - len(args.defaults):]) if args.defaults else set()
    for param, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is not None:
            defaulted.add(param.arg)
    return {
        "positional": positional,
        "vararg": args.vararg.arg if args.vararg else None,
        "kwonly": sorted(p.arg for p in args.kwonlyargs),
        "kwarg": args.kwarg.arg if args.kwarg else None,
        "defaulted": sorted(defaulted),
    }


def _render(signature: dict) -> str:
    parts = list(signature["positional"])
    if signature["vararg"]:
        parts.append("*" + signature["vararg"])
    elif signature["kwonly"]:
        parts.append("*")
    parts.extend(signature["kwonly"])
    if signature["kwarg"]:
        parts.append("**" + signature["kwarg"])
    marked = [f"{p}=..." if p in signature["defaulted"] else p for p in parts]
    return "(" + ", ".join(marked) + ")"


def _compare_signatures(label: str, reference_fn, scaffold_fn) -> list:
    want = _signature(reference_fn)
    got = _signature(scaffold_fn)
    if want == got:
        return []
    return [
        f"scaffold.py line {scaffold_fn.lineno}: {label} signature has drifted from "
        f"reference.py. reference.py defines {label}{_render(want)}, scaffold.py "
        f"defines {label}{_render(got)}. Make the scaffold match, or the student "
        f"solves a different problem from the one the reference solves."
    ]


def _near(name: str, candidates) -> str:
    """A hint aimed at the usual cause: a rename or a casing slip."""
    folded = name.replace("_", "").lower()
    close = [c for c in candidates if c.replace("_", "").lower() == folded]
    if close:
        return f" Did you mean {close[0]!r}?"
    return ""


# The checks


def check_imports(name: str, tree: ast.Module, locals_allowed: frozenset) -> list:
    """
    Root import names only, never dotted ones.

    Resolving `pkg.sub` would import `pkg` to find the child, which puts
    arbitrary module-level code back into what is supposed to be a static pass.
    The root name is all we need: it is what pip would have had to install.
    """
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = [(alias.name.split(".")[0], node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue  # relative import, and node.module may be None
            roots = [((node.module or "").split(".")[0], node.lineno)]
        else:
            continue
        for root, lineno in roots:
            if not root or root in STDLIB or root in locals_allowed:
                continue
            allowed = ", ".join(sorted(locals_allowed))
            problems.append(
                f"{name} line {lineno}: imports {root!r}, which is not available. "
                f"Exercises run with the standard library plus {allowed} "
                f"and nothing else, because installing anything is not an option."
            )
    return problems


def check_reference_is_complete(tree: ast.Module, source: str) -> list:
    """reference.py is a worked solution, so it cannot still be a stub."""
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        raised = node.exc
        if isinstance(raised, ast.Call):
            raised = raised.func
        if isinstance(raised, ast.Name) and raised.id == "NotImplementedError":
            problems.append(
                f"reference.py line {node.lineno}: still raises NotImplementedError. "
                f"reference.py is the complete worked solution; the unfinished bodies "
                f"belong in scaffold.py."
            )
    for number, line in enumerate(source.splitlines(), start=1):
        if "TODO" in line:
            problems.append(
                f"reference.py line {number}: contains TODO. A worked solution has "
                f"nothing left to do; move the note to the lesson prose or finish it."
            )
    return problems


def check_structure(test_tree, scaffold_tree, reference_tree) -> list:
    """
    Every name test.py imports from solution must exist in both files, be the
    same kind of thing in both, and carry the same signature in both.
    """
    wanted = []
    for node in ast.walk(test_tree):
        if isinstance(node, ast.ImportFrom) and node.module == "solution" and not node.level:
            for alias in node.names:
                if alias.name != "*":
                    wanted.append((alias.name, node.lineno))

    if not wanted:
        return [
            "test.py: imports nothing from solution. The test must grade the "
            "student's file: add `from solution import <name>`."
        ]

    scaffold_defs = _definitions(scaffold_tree)
    reference_defs = _definitions(reference_tree)
    problems = []

    for name, lineno in wanted:
        for filename, defs in (("scaffold.py", scaffold_defs), ("reference.py", reference_defs)):
            if name not in defs:
                available = sorted(defs)
                problems.append(
                    f"{filename}: does not define {name!r}, which test.py imports at "
                    f"line {lineno}.{_near(name, available)} {filename} defines: "
                    f"{', '.join(available) or '(nothing)'}."
                )
        if name not in scaffold_defs or name not in reference_defs:
            continue

        scaffold_node = scaffold_defs[name]
        reference_node = reference_defs[name]
        if _kind(scaffold_node) != _kind(reference_node):
            problems.append(
                f"scaffold.py line {scaffold_node.lineno}: {name!r} is a "
                f"{_kind(scaffold_node)} here and a {_kind(reference_node)} in "
                f"reference.py. The two files must agree on what {name!r} is."
            )
            continue

        if isinstance(scaffold_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            problems.extend(_compare_signatures(name, reference_node, scaffold_node))
        elif isinstance(scaffold_node, ast.ClassDef):
            reference_methods = {
                m.name: m
                for m in reference_node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            for method in scaffold_node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                twin = reference_methods.get(method.name)
                if twin is not None:
                    problems.extend(
                        _compare_signatures(f"{name}.{method.name}", twin, method)
                    )

    return problems


def check_scaffold_fails(exercise_dir, lib_dir, scaffold, test, timeout) -> list:
    """
    The scaffold must not pass its own test.

    This is the check that decides whether the exercise teaches anything. A
    scaffold that passes means the student's work is already done, and no amount
    of careful prose makes up for that.
    """
    scratch = tempfile.mkdtemp(prefix="learn-scaffold-")
    try:
        shutil.copytree(
            exercise_dir,
            scratch,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        copy_lib(lib_dir, scratch)
        shutil.copy(os.path.join(scratch, scaffold), os.path.join(scratch, SOLUTION_FILENAME))

        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        try:
            completed = subprocess.run(
                [sys.executable, test],
                cwd=scratch,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return [
                f"{scaffold}: running {test} against the scaffold did not finish within "
                f"{timeout}s. A scaffold whose bodies raise NotImplementedError returns "
                f"immediately, so this is a loop in {test} or in the scaffold that never "
                f"terminates."
            ]

        output = f"{completed.stdout}{completed.stderr}"
        problems = []
        if "Ran 0 tests" in output:
            problems.append(
                f"{test}: ran 0 tests. unittest reports success on an empty suite, so a "
                f"test file whose methods are not named test_* passes everything. Name "
                f"them test_<something>."
            )
        if completed.returncode == 0:
            tail = "\n".join(output.strip().splitlines()[-8:])
            problems.append(
                f"{scaffold}: passes {test}, so the exercise asks the student for nothing. "
                f"The scaffold must leave the work undone: keep the signatures and "
                f"docstrings, and let the bodies raise NotImplementedError."
                + (f"\n{tail}" if tail else "")
            )
        return problems
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--lib", default="")
    parser.add_argument("--scaffold", default="scaffold.py")
    parser.add_argument("--reference", default="reference.py")
    parser.add_argument("--test", default="test.py")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    locals_allowed = local_modules(args.lib)
    problems = []
    trees = {}

    # (a) Syntax pre-flight on every Python file in the exercise, so a typo is
    # reported as a file and a line rather than as unittest output.
    for name in sorted(os.listdir(args.dir)):
        if not name.endswith(".py"):
            continue
        if (
            name.startswith("solutions-")
            or name.startswith("solution-")
            or name.startswith("solutions_")
        ):
            continue
        path = os.path.join(args.dir, name)
        if not os.path.isfile(path):
            continue
        tree, problem = preflight(name, read_source(path), path)
        if problem:
            problems.append(problem)
        else:
            trees[name] = tree
            problems.extend(check_imports(name, tree, locals_allowed))

    reference_tree = trees.get(args.reference)
    scaffold_tree = trees.get(args.scaffold)
    test_tree = trees.get(args.test)

    # (d) The reference is a finished solution, not a stub with better docstrings.
    if reference_tree is not None:
        problems.extend(
            check_reference_is_complete(
                reference_tree, read_source(os.path.join(args.dir, args.reference))
            )
        )

    # (c) The scaffold and the reference must present the same surface.
    if test_tree is not None and scaffold_tree is not None and reference_tree is not None:
        problems.extend(check_structure(test_tree, scaffold_tree, reference_tree))

    # (b) The scaffold must fail. Skipped only when a file will not parse,
    # because the syntax error above already says everything useful.
    if scaffold_tree is not None and test_tree is not None:
        problems.extend(
            check_scaffold_fails(
                args.dir, args.lib, args.scaffold, args.test, args.timeout
            )
        )

    # The caller skips its own reference run when a file did not parse, because
    # the message above already names the file and the line.
    json.dump({"problems": problems, "parsed": sorted(trees)}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
