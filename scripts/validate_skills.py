#!/usr/bin/env python3
"""Validate the skills catalog, frontmatter, layer rules, plugin manifests, and references.

Exit code 0 if everything passes; non-zero (1) on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _lib.catalog import (
    REPO_ROOT,
    SKILLS_DIR,
    VALID_LAYERS,
    Catalog,
    SkillEntry,
    find_reference_links,
    load_catalog,
    parse_frontmatter,
)

CLAUDE_PLUGIN_PATH = (
    REPO_ROOT / "plugins" / "carto-skills-claude" / ".claude-plugin" / "plugin.json"
)
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def check_catalog_filesystem(cat: Catalog, errors: list[str]) -> None:
    cat_paths = {Path(s.path).name for s in cat.skills}
    fs_dirs = {
        p.name
        for p in SKILLS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_")
    }
    for name in cat_paths - fs_dirs:
        _err(errors, f"catalog references missing directory: skills/{name}")
    for name in fs_dirs - cat_paths:
        _err(errors, f"directory not in catalog: skills/{name}")
    for s in cat.skills:
        if not s.skill_md.exists():
            _err(errors, f"missing SKILL.md for {s.name} at {s.skill_md.relative_to(REPO_ROOT)}")


def check_frontmatter(cat: Catalog, errors: list[str]) -> None:
    for s in cat.skills:
        if not s.skill_md.exists():
            continue
        text = s.skill_md.read_text()
        fm = parse_frontmatter(text)
        if fm is None:
            _err(errors, f"{s.name}: SKILL.md is missing YAML frontmatter")
            continue
        for required in ("name", "description", "license"):
            if required not in fm:
                _err(errors, f"{s.name}: frontmatter missing '{required}'")
        if fm.get("name") != s.name:
            _err(
                errors,
                f"{s.name}: frontmatter name '{fm.get('name')}' != catalog name",
            )


def check_layer_rules(cat: Catalog, errors: list[str]) -> None:
    by_name = cat.by_name()
    utility = {s.name for s in cat.skills if s.layer == "utility"}
    platform = {s.name for s in cat.skills if s.layer == "platform"}
    for s in cat.skills:
        if s.layer not in VALID_LAYERS:
            _err(errors, f"{s.name}: invalid layer '{s.layer}'")
            continue
        for dep in s.dependencies:
            if dep not in by_name:
                _err(errors, f"{s.name}: dependency '{dep}' not in catalog")
                continue
            dep_layer = by_name[dep].layer
            if s.layer == "utility":
                _err(errors, f"{s.name}: utility skill cannot have dependencies")
            elif s.layer == "platform" and dep_layer != "utility":
                _err(
                    errors,
                    f"{s.name}: platform skill may only depend on utility, not '{dep_layer}'",
                )
            elif s.layer == "use-case" and dep_layer not in ("utility", "platform"):
                _err(
                    errors,
                    f"{s.name}: use-case skill cannot depend on '{dep_layer}'",
                )


def check_plugin_manifest(cat: Catalog, errors: list[str]) -> None:
    if not CLAUDE_PLUGIN_PATH.exists():
        _err(errors, f"missing Claude plugin manifest at {CLAUDE_PLUGIN_PATH.relative_to(REPO_ROOT)}")
        return
    with CLAUDE_PLUGIN_PATH.open() as f:
        manifest = json.load(f)
    declared = manifest.get("skills", [])
    expected = {s.path for s in cat.skills}
    # plugin paths are relative to plugin.json's directory; resolve them against repo root
    plugin_dir = CLAUDE_PLUGIN_PATH.parent
    actual = {
        str((plugin_dir / p).resolve().relative_to(REPO_ROOT)) for p in declared
    }
    if actual != expected:
        missing = expected - actual
        extra = actual - expected
        if missing:
            _err(errors, f"plugin manifest missing skills: {sorted(missing)}")
        if extra:
            _err(errors, f"plugin manifest has unexpected skills: {sorted(extra)}")


def check_marketplace(cat: Catalog, errors: list[str]) -> None:
    if not MARKETPLACE_PATH.exists():
        _err(errors, f"missing marketplace at {MARKETPLACE_PATH.relative_to(REPO_ROOT)}")
        return
    with MARKETPLACE_PATH.open() as f:
        mp = json.load(f)
    plugins = mp.get("plugins", [])
    if not plugins:
        _err(errors, "marketplace.json has no plugins")
        return
    plugin = next((p for p in plugins if p.get("name") == "carto-skills"), None)
    if plugin is None:
        _err(errors, "marketplace.json has no plugin named 'carto-skills'")
        return
    declared = plugin.get("skills", [])
    source = plugin.get("source", "./")
    source_dir = (REPO_ROOT / source).resolve()
    actual = {
        str((source_dir / p).resolve().relative_to(REPO_ROOT)) for p in declared
    }
    expected = {s.path for s in cat.skills}
    if actual != expected:
        missing = expected - actual
        extra = actual - expected
        if missing:
            _err(errors, f"marketplace.json missing skills: {sorted(missing)}")
        if extra:
            _err(errors, f"marketplace.json has unexpected skills: {sorted(extra)}")


def check_reference_integrity(cat: Catalog, errors: list[str]) -> None:
    for s in cat.skills:
        if not s.skill_md.exists():
            continue
        text = s.skill_md.read_text()
        linked = set(find_reference_links(text))
        ref_dir = s.abs_path / "references"
        existing = (
            {f"references/{p.name}" for p in ref_dir.iterdir() if p.is_file()}
            if ref_dir.is_dir()
            else set()
        )
        for link in linked:
            if not (s.abs_path / link).exists():
                _err(errors, f"{s.name}: SKILL.md links missing reference '{link}'")
        for orphan in existing - linked:
            _err(errors, f"{s.name}: orphaned reference file '{orphan}' (not linked from SKILL.md)")


def main() -> int:
    errors: list[str] = []
    try:
        cat = load_catalog()
    except Exception as e:
        print(f"FAIL: could not load catalog: {e}", file=sys.stderr)
        return 1

    check_catalog_filesystem(cat, errors)
    check_frontmatter(cat, errors)
    check_layer_rules(cat, errors)
    check_plugin_manifest(cat, errors)
    check_marketplace(cat, errors)
    check_reference_integrity(cat, errors)

    if errors:
        print(f"validate_skills: {len(errors)} error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"validate_skills: OK ({len(cat.skills)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
