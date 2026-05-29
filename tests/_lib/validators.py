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


_TS_AMBIENT_SHIM = """\
// Auto-generated ambient declarations for docs-style TS snippet validation.
// Lets unknown package imports and `import.meta.env` resolve to `any` so the
// validator can check syntax without requiring node_modules.
declare module '*';
interface ImportMeta {
  readonly env: Record<string, string>;
}
declare const process: { env: Record<string, string> };
"""

_HAS_IMPORT_OR_EXPORT_RE = re.compile(r"^\s*(?:import|export)\b", re.MULTILINE)

# tsc emits diagnostics like:  snippet.ts(1,5): error TS2304: Cannot find name 'foo'.
_TSC_DIAGNOSTIC_RE = re.compile(r"^(?P<location>\S+):\s*error TS(?P<code>\d+):", re.MULTILINE)


def _wrap_ts_for_module_context(code: str) -> str:
    """Append `export {}` if the snippet has no imports/exports.

    A file without any top-level import/export is treated by TS as a global
    script — top-level `await` is rejected (TS1375), and the snippet leaks
    its top-level identifiers into a global namespace shared with other
    snippets. Forcing module context fixes both.
    """
    if not _HAS_IMPORT_OR_EXPORT_RE.search(code):
        return code.rstrip() + "\n\nexport {};\n"
    return code


def _filter_syntax_errors(tsc_output: str) -> list[str]:
    """Extract only true syntax (parser) errors from tsc diagnostics.

    tsc reports diagnostics as TS1xxx (syntax/parser) and TS2xxx+ (binder /
    checker / semantic). Docs-style snippets routinely elide imports and
    reference identifiers from surrounding prose — those are *valid syntax*
    that just wouldn't compile as a standalone program. We only fail on TS1xxx
    so the validator behaves like the bash and SQL validators (parse, don't
    typecheck).
    """
    syntax_blocks: list[str] = []
    lines = tsc_output.splitlines()
    keep = False
    for line in lines:
        m = _TSC_DIAGNOSTIC_RE.match(line)
        if m:
            # Real parser errors are TS1000–1999. Everything else (TS2xxx,
            # TS17xxx, TS18xxx, …) is binder/checker territory and not what
            # docs-style snippet validation is about.
            code = int(m.group("code"))
            keep = 1000 <= code < 2000
        if keep:
            syntax_blocks.append(line)
    return syntax_blocks


def validate_typescript(code: str, jsx: bool = False) -> str | None:
    """Syntax-check a TS / TSX snippet from documentation.

    Validates *syntax*, not type correctness — matches the leniency of the
    bash and SQL validators. Unknown imports resolve to `any` via an ambient
    `declare module '*'` shim; `import.meta.env` and `process.env` are
    recognized so config-reading snippets don't fail.

    Use `lang=ts skip` (or `tsx skip`) on a fenced block to opt out entirely.
    """
    if shutil.which("tsc") is None:
        warn("tsc not on PATH; skipping typescript snippets (install: npm i -g typescript)")
        return None

    code = _wrap_ts_for_module_context(code)

    # Use a fresh tempdir so the tsconfig + ambient shim sit next to the
    # snippet and are picked up by tsc's project resolution.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        suffix = ".tsx" if jsx else ".ts"
        snippet_path = tmp / f"snippet{suffix}"
        shim_path = tmp / "ambient.d.ts"
        tsconfig_path = tmp / "tsconfig.json"

        snippet_path.write_text(code)
        shim_path.write_text(_TS_AMBIENT_SHIM)

        # Compiler options chosen to validate syntax without demanding
        # standalone programs:
        #   noEmit                  don't write .js
        #   target/module esnext    accept modern syntax + top-level await
        #   moduleResolution bundler resolve like Vite/webpack
        #   jsx react-jsx           parse JSX without needing a React import
        #   noImplicitAny false     untyped params are fine in docs prose
        #   skipLibCheck            don't typecheck DOM / lib.d.ts
        #   types []                don't auto-include @types/node etc.
        #   isolatedModules         catches truly broken module structure
        tsconfig = {
            "compilerOptions": {
                "noEmit": True,
                "target": "esnext",
                "module": "esnext",
                "moduleResolution": "bundler",
                "jsx": "react-jsx",
                "noImplicitAny": False,
                "skipLibCheck": True,
                "types": [],
                "isolatedModules": True,
                "allowJs": False,
                "lib": ["esnext", "dom"],
                "allowSyntheticDefaultImports": True,
                "esModuleInterop": True,
            },
            "include": [snippet_path.name, shim_path.name],
        }
        tsconfig_path.write_text(json.dumps(tsconfig))

        # Run tsc with cwd inside the tempdir so diagnostic paths come out
        # relative (e.g. `snippet.ts(1,5)`) instead of an absolute /var/folders/…
        # mess that's hard to read in CI logs.
        result = subprocess.run(
            ["tsc", "--project", "tsconfig.json"],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raw = (result.stdout.strip() or result.stderr.strip())
            syntax_errors = _filter_syntax_errors(raw)
            if syntax_errors:
                return "typescript syntax error: " + " | ".join(syntax_errors)
    return None
