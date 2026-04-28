"""Shared catalog loader and frontmatter parser."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "skills" / "catalog.json"
SKILLS_DIR = REPO_ROOT / "skills"

VALID_LAYERS = ("utility", "platform", "use-case")


@dataclass
class SkillEntry:
    name: str
    layer: str
    dependencies: list[str]
    description: str
    path: str

    @property
    def abs_path(self) -> Path:
        return REPO_ROOT / self.path

    @property
    def skill_md(self) -> Path:
        return self.abs_path / "SKILL.md"


@dataclass
class Catalog:
    version: str
    skills: list[SkillEntry]

    def by_name(self) -> dict[str, SkillEntry]:
        return {s.name: s for s in self.skills}


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    with path.open() as f:
        data = json.load(f)
    skills = [
        SkillEntry(
            name=s["name"],
            layer=s["layer"],
            dependencies=list(s.get("dependencies", [])),
            description=s["description"],
            path=s["path"],
        )
        for s in data["skills"]
    ]
    return Catalog(version=data["version"], skills=skills)


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse YAML-like frontmatter. Tolerates simple scalar fields only."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    out: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


REFERENCE_LINK_RE = re.compile(r"\[[^\]]+\]\((references/[^)]+)\)")


def find_reference_links(text: str) -> Iterable[str]:
    return REFERENCE_LINK_RE.findall(text)
