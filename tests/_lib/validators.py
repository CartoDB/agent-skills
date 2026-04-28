"""Per-language snippet validators.

Each validator returns None on success, or a string error message on failure.
Validators that require optional dependencies degrade to a soft-skip with a
warning rather than failing the run.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

try:
    import logging

    import sqlglot  # type: ignore
    from sqlglot.errors import ParseError as _SqlglotParseError  # type: ignore

    # sqlglot logs "falling back to parsing as a Command" warnings for DDL it
    # doesn't fully model (e.g., GRANT, CREATE ROLE). These are non-failures —
    # silence them so CI output stays clean.
    logging.getLogger("sqlglot").setLevel(logging.ERROR)
except ImportError:  # pragma: no cover
    sqlglot = None
    _SqlglotParseError = Exception


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def validate_python(code: str) -> str | None:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"python syntax error: {e.msg} (line {e.lineno})"
    return None


_BASH_PLACEHOLDER_RE = re.compile(r"<([a-zA-Z][\w\-|]*)>")


def _strip_bash_placeholders(code: str) -> str:
    """Replace `<placeholder>` tokens (common in command synopses) with safe values
    so that `bash -n` doesn't read them as redirections."""
    return _BASH_PLACEHOLDER_RE.sub(r"PLACEHOLDER_\1", code)


def validate_bash(code: str) -> str | None:
    if shutil.which("bash") is None:
        warn("bash not on PATH; skipping bash snippets")
        return None
    cleaned = _strip_bash_placeholders(code)
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(cleaned)
        path = f.name
    try:
        result = subprocess.run(
            ["bash", "-n", path], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return f"bash syntax error: {result.stderr.strip()}"
    finally:
        Path(path).unlink(missing_ok=True)
    return None


def validate_json(code: str) -> str | None:
    # Documentation JSON often contains `...` to indicate truncation (either on
    # its own line or inline as `{ ... }` placeholder), or `//` comments that
    # aren't strict JSON. Skip those blocks rather than fail.
    if "..." in code or "// " in code:
        return None
    try:
        json.loads(code)
    except json.JSONDecodeError as e:
        return f"json error: {e.msg} (line {e.lineno})"
    return None


def validate_yaml(code: str) -> str | None:
    if yaml is None:
        warn("PyYAML not installed; skipping yaml snippets")
        return None
    try:
        yaml.safe_load(code)
    except yaml.YAMLError as e:
        return f"yaml error: {e}"
    return None


_SQL_JINJA_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_SQL_DOLLAR_RE = re.compile(r"\$\{([^}]+)\}")


def _strip_sql_placeholders(code: str) -> str:
    """Replace Jinja `{{ var }}` and shell `${var}` placeholders with bare
    identifiers so sqlglot can parse the surrounding SQL. Bare identifiers (not
    string literals) — the source SQL controls whether quotes appear around the
    placeholder."""
    code = _SQL_JINJA_RE.sub("PLACEHOLDER", code)
    code = _SQL_DOLLAR_RE.sub("PLACEHOLDER", code)
    return code


def validate_sql(code: str, dialect: str | None = None) -> str | None:
    if sqlglot is None:
        warn("sqlglot not installed; skipping sql snippets")
        return None
    cleaned = _strip_sql_placeholders(code)
    try:
        sqlglot.parse(cleaned, read=dialect)
    except _SqlglotParseError as e:
        suffix = f" ({dialect})" if dialect else ""
        return f"sql parse error{suffix}: {e}"
    except Exception as e:
        suffix = f" ({dialect})" if dialect else ""
        return f"sql error{suffix}: {e}"
    return None


def validate_typescript(code: str) -> str | None:
    if shutil.which("tsc") is None:
        warn("tsc not on PATH; skipping typescript snippets (Phase 1: not blocking)")
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            ["tsc", "--noEmit", "--strict", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"typescript error: {result.stdout.strip() or result.stderr.strip()}"
    finally:
        Path(path).unlink(missing_ok=True)
    return None
