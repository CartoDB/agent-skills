#!/usr/bin/env python3
"""Generate plugin manifests from skills/catalog.json.

Today this writes the Claude Code plugin manifest. Codex/Gemini manifests are
added in Phase 2.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from _lib.catalog import REPO_ROOT, load_catalog

CLAUDE_PLUGIN_DIR = REPO_ROOT / "plugins" / "carto-skills-claude" / ".claude-plugin"
CLAUDE_PLUGIN_PATH = CLAUDE_PLUGIN_DIR / "plugin.json"


def relative_skill_path(plugin_dir: Path, skill_path: str) -> str:
    skill_abs = (REPO_ROOT / skill_path).resolve()
    return os.path.relpath(skill_abs, plugin_dir.resolve())


def write_claude_plugin() -> None:
    cat = load_catalog()
    manifest = {
        "name": "carto-skills",
        "description": "CARTO skills bundle for Claude Code — see skills/catalog.json for the layered tier breakdown.",
        "version": cat.version,
        "skills": [relative_skill_path(CLAUDE_PLUGIN_DIR, s.path) for s in cat.skills],
    }
    CLAUDE_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    with CLAUDE_PLUGIN_PATH.open("w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {CLAUDE_PLUGIN_PATH.relative_to(REPO_ROOT)}")


def main() -> int:
    write_claude_plugin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
