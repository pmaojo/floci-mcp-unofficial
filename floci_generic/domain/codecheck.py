"""What agent-written code may contain before it is allowed to run at all (a guardrail, not isolation)."""
import ast

ALLOWED_IMPORTS = {
    "json", "re", "math", "datetime", "collections", "itertools", "statistics", "base64", "textwrap",
    "string", "functools", "decimal", "time", "uuid", "hashlib", "fnmatch", "operator", "typing",
}
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "exit", "quit", "help",
}


def _import_problems(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [f"import {a.name!r} is not allowed" for a in node.names if a.name.split(".")[0] not in ALLOWED_IMPORTS]
    module = (node.module or "")  # ast.ImportFrom
    if module.split(".")[0] not in ALLOWED_IMPORTS or node.level:
        return [f"import from {node.module!r} is not allowed"]
    return []


def _name_problems(node: ast.Name) -> list[str]:
    dunder = node.id.startswith("__") and node.id != "__name__"
    return [f"name {node.id!r} is not allowed"] if node.id in FORBIDDEN_NAMES or dunder else []


def _attribute_problems(node: ast.Attribute) -> list[str]:
    return [f"attribute {node.attr!r} is not allowed"] if node.attr.startswith("__") else []


_CHECKS = {
    ast.Import: _import_problems, ast.ImportFrom: _import_problems,
    ast.Name: _name_problems, ast.Attribute: _attribute_problems,
}


def validate(code: str) -> list[str]:
    """Problems that stop the code from running at all. Empty list means it may run."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc.msg} (line {exc.lineno})"]
    problems: set[str] = set()
    for node in ast.walk(tree):
        check = _CHECKS.get(type(node))
        if check:
            problems.update(check(node))
    return sorted(problems)
