#!/usr/bin/env python3
"""Extract fenced code blocks from skills/**/*.md and validate them per language.

Writes snippet-errors.json on failure. Exit non-zero if any snippet fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Make _lib importable when invoked from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.validators import (  # noqa: E402
    validate_bash,
    validate_json,
    validate_python,
    validate_sql,
    validate_typescript,
    validate_yaml,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# A fenced block: ``` followed by an info string, content, then ```
FENCE_RE = re.compile(
    r"^```([^\n]*)\n(.*?)^```",
    re.DOTALL | re.MULTILINE,
)


def parse_info_string(info: str) -> tuple[str, dict[str, str]]:
    """Split an info string like 'sql bigquery' into (lang, attrs)."""
    parts = info.strip().split()
    if not parts:
        return "", {}
    lang = parts[0].lower()
    attrs: dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, _, v = p.partition("=")
            attrs[k] = v
        else:
            attrs[p] = "true"
    return lang, attrs


def dispatch(lang: str, attrs: dict[str, str], code: str) -> str | None:
    # Authors can opt a fenced block out of validation with `lang=... skip`.
    # Use sparingly — for fragments that aren't valid standalone (e.g. JSON
    # excerpts inside a TS block, or partial syntax used purely to illustrate
    # a concept).
    if attrs.get("skip"):
        return None
    if lang in ("python", "py"):
        return validate_python(code)
    if lang in ("bash", "sh", "shell"):
        return validate_bash(code)
    if lang == "json":
        return validate_json(code)
    if lang in ("yaml", "yml"):
        return validate_yaml(code)
    if lang == "sql":
        dialect = next(
            (d for d in ("bigquery", "snowflake", "postgres", "redshift", "databricks", "duckdb") if d in attrs),
            None,
        )
        return validate_sql(code, dialect)
    if lang in ("ts", "typescript"):
        return validate_typescript(code, jsx=False)
    if lang == "tsx":
        return validate_typescript(code, jsx=True)
    # Unknown / untagged: skip silently. Untagged blocks are allowed in prose.
    return None


def main() -> int:
    if not SKILLS_DIR.exists():
        print(f"no skills/ directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    errors: list[dict[str, str]] = []
    snippet_count = 0
    skipped_untagged = 0

    for md in sorted(SKILLS_DIR.rglob("*.md")):
        text = md.read_text()
        for m in FENCE_RE.finditer(text):
            info = m.group(1)
            code = m.group(2)
            lang, attrs = parse_info_string(info)
            if not lang:
                skipped_untagged += 1
                continue
            snippet_count += 1
            err = dispatch(lang, attrs, code)
            if err:
                # Compute approximate line number of the fence open.
                line_no = text.count("\n", 0, m.start()) + 1
                errors.append(
                    {
                        "file": str(md.relative_to(REPO_ROOT)),
                        "line": str(line_no),
                        "lang": lang,
                        "error": err,
                    }
                )

    if errors:
        out = REPO_ROOT / "snippet-errors.json"
        with out.open("w") as f:
            json.dump(errors, f, indent=2)
        print(
            f"validate_snippets: {len(errors)} error(s) across {snippet_count} snippets",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  - {e['file']}:{e['line']} [{e['lang']}] {e['error']}", file=sys.stderr)
        return 1

    print(
        f"validate_snippets: OK ({snippet_count} snippets validated, "
        f"{skipped_untagged} untagged skipped)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
