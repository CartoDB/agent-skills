#!/usr/bin/env python3
"""Generate harness manifests from skills/catalog.json.

Writes:
- plugins/carto-skills-claude/.claude-plugin/plugin.json (Claude plugin)
- .codex-plugin/plugin.json (Codex plugin, repo-root per MotherDuck pattern)
- gemini-extension.json (Gemini extension manifest)
- commands/carto/<skill>.toml (one Gemini command per skill)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from _lib.catalog import REPO_ROOT, SkillEntry, load_catalog

CLAUDE_PLUGIN_DIR = REPO_ROOT / "plugins" / "carto-skills-claude" / ".claude-plugin"
CLAUDE_PLUGIN_PATH = CLAUDE_PLUGIN_DIR / "plugin.json"

CODEX_PLUGIN_DIR = REPO_ROOT / ".codex-plugin"
CODEX_PLUGIN_PATH = CODEX_PLUGIN_DIR / "plugin.json"

GEMINI_EXTENSION_PATH = REPO_ROOT / "gemini-extension.json"
GEMINI_COMMANDS_DIR = REPO_ROOT / "commands" / "carto"


def relative_skill_path(from_dir: Path, skill_path: str) -> str:
    skill_abs = (REPO_ROOT / skill_path).resolve()
    return os.path.relpath(skill_abs, from_dir.resolve())


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


# --------------- Claude ---------------


def write_claude_plugin() -> None:
    cat = load_catalog()
    manifest = {
        "name": "carto-skills",
        "description": "CARTO skills bundle for Claude Code — see skills/catalog.json for the layered tier breakdown.",
        "skills": [relative_skill_path(CLAUDE_PLUGIN_DIR, s.path) for s in cat.skills],
    }
    _write_json(CLAUDE_PLUGIN_PATH, manifest)


# --------------- Codex ---------------


def write_codex_plugin() -> None:
    manifest = {
        "name": "carto-skills",
        "description": "CARTO skills for agents and developers: connect to a data warehouse, explore schemas, write spatial SQL, build analytics workflows, subscribe to Data Observatory data, and administer the platform.",
        "author": {
            "name": "CARTO",
            "url": "https://carto.com",
        },
        "homepage": "https://github.com/CartoDB/carto-agent-skills",
        "repository": "https://github.com/CartoDB/carto-agent-skills",
        "license": "MIT",
        "keywords": [
            "carto",
            "geospatial",
            "spatial-sql",
            "data-warehouse",
            "bigquery",
            "snowflake",
            "redshift",
            "postgres",
            "databricks",
            "data-observatory",
            "cli",
        ],
        "skills": "./skills/",
        "interface": {
            "displayName": "CARTO Skills",
            "shortDescription": "Connect, explore, query, and operate the CARTO Geospatial Cloud.",
            "longDescription": (
                "A packaged CARTO skill catalog for managing CARTO Geospatial Cloud "
                "resources via the carto-cli — installing and authenticating, connecting "
                "BigQuery / Snowflake / Redshift / Postgres / Databricks, exploring "
                "schemas, writing spatial SQL with dialect-specific guidance, importing "
                "and exporting data, building analytics workflows, discovering Data "
                "Observatory datasets, and administering the org."
            ),
            "developerName": "CARTO",
            "category": "Productivity",
            "capabilities": ["Read"],
            "websiteURL": "https://carto.com",
            "defaultPrompt": [
                "Use CARTO Skills to inspect my data warehouse schemas and recommend a spatial SQL approach.",
                "Use CARTO Skills to plan a workflow that imports a file, builds a tileset, and schedules a refresh.",
            ],
        },
    }
    _write_json(CODEX_PLUGIN_PATH, manifest)


# --------------- Gemini ---------------


def write_gemini_extension() -> None:
    manifest = {
        "name": "carto-skills",
        "description": "CARTO skills for Gemini CLI: connect, explore live schemas, write spatial SQL, manage workflows, subscribe to Data Observatory data, and administer the org.",
        "contextFileName": "GEMINI.md",
        "plan": {
            "directory": ".gemini/plans",
        },
    }
    _write_json(GEMINI_EXTENSION_PATH, manifest)


def _gemini_command_toml(skill: SkillEntry) -> str:
    """Render a Gemini command TOML for one skill."""
    description = skill.description.rstrip(".") + " (carto-skills)"
    skill_md = (REPO_ROOT / skill.path / "SKILL.md").relative_to(REPO_ROOT)
    prompt = (
        f"Apply the `{skill.name}` skill from the carto-skills catalog "
        f"to the user's request.\n\n"
        f"Required behavior:\n"
        f"- Read the skill's main guidance at `{skill_md}` first.\n"
        f"- Follow the skill's reference files (under `{skill.path}/references/`) "
        f"for depth on specific topics.\n"
        f"- Stay within the skill's stated scope; if the request belongs to a "
        f"different skill, say which one and stop.\n"
        f"- For machine-parseable CLI output, always pass `--json`.\n"
    )
    # TOML escape: double quotes inside triple-double-quoted strings need care.
    # Use unescaped triple-quoted literals; backslashes are not interpreted in
    # TOML's basic strings, but we use literal triple-quotes to avoid escaping.
    return (
        f'description = "{description}"\n\n'
        f'prompt = """\n{prompt}"""\n'
    )


def write_gemini_commands() -> None:
    cat = load_catalog()
    GEMINI_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    expected = {f"{s.name}.toml" for s in cat.skills}
    # Remove stale TOMLs for skills that no longer exist.
    if GEMINI_COMMANDS_DIR.exists():
        for existing in GEMINI_COMMANDS_DIR.glob("*.toml"):
            if existing.name not in expected:
                existing.unlink()
                print(f"removed stale {existing.relative_to(REPO_ROOT)}")
    for skill in cat.skills:
        path = GEMINI_COMMANDS_DIR / f"{skill.name}.toml"
        path.write_text(_gemini_command_toml(skill))
        print(f"wrote {path.relative_to(REPO_ROOT)}")


# --------------- entry ---------------


def main() -> int:
    write_claude_plugin()
    write_codex_plugin()
    write_gemini_extension()
    write_gemini_commands()
    return 0


if __name__ == "__main__":
    sys.exit(main())
