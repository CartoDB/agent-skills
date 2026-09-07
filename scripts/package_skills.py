#!/usr/bin/env python3
"""Package every skill in skills/catalog.json as an uploadable zip.

Some harnesses have no git or marketplace integration and only accept a
skill through a web upload form: Claude.ai (Customize > Skills > Upload),
Gemini Enterprise (Upload skill, Markdown or ZIP), and the Claude Skills
API. Those forms want one zip per skill with SKILL.md at the archive root.

This script builds those archives. It is run by the release workflow, which
attaches the output to a GitHub Release, so the zips are never committed.

Writes to --out (default: dist/):
- <skill-name>.zip          one per skill, SKILL.md at the root
- carto-skills-all.zip      every skill, each under its own top-level folder
- manifest.json             name, layer, dependencies, file, sha256, size
- SHA256SUMS                sha256sum-compatible checksum list

Archives are deterministic: entries are sorted and timestamps are fixed, so
re-running on the same tree produces byte-identical zips.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

from _lib.catalog import REPO_ROOT, SkillEntry, load_catalog

DEFAULT_OUT = REPO_ROOT / "dist"
BUNDLE_NAME = "carto-skills-all.zip"

# Fixed timestamp for reproducible archives (zip cannot represent < 1980).
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)

SKIP_DIR_NAMES = {"__pycache__", ".git", "node_modules", ".pytest_cache"}
SKIP_FILE_NAMES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc"}


def iter_skill_files(skill_dir: Path) -> list[Path]:
    """All files under a skill directory, sorted, minus junk."""
    files: list[Path] = []
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(skill_dir).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        if p.name in SKIP_FILE_NAMES or p.suffix in SKIP_SUFFIXES:
            continue
        files.append(p)
    return files


def _add_file(zf: zipfile.ZipFile, src: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    # -rw-r--r-- regular file; keeps archives identical across checkouts.
    info.external_attr = (0o100644 << 16)
    with src.open("rb") as f:
        zf.writestr(info, f.read())


def write_skill_zip(skill: SkillEntry, out_dir: Path) -> Path:
    if not skill.skill_md.is_file():
        raise SystemExit(f"{skill.name}: missing {skill.skill_md.relative_to(REPO_ROOT)}")
    dest = out_dir / f"{skill.name}.zip"
    with zipfile.ZipFile(dest, "w") as zf:
        for src in iter_skill_files(skill.abs_path):
            _add_file(zf, src, src.relative_to(skill.abs_path).as_posix())
    return dest


def write_bundle_zip(skills: list[SkillEntry], out_dir: Path) -> Path:
    dest = out_dir / BUNDLE_NAME
    with zipfile.ZipFile(dest, "w") as zf:
        for skill in skills:
            for src in iter_skill_files(skill.abs_path):
                arcname = f"{skill.name}/{src.relative_to(skill.abs_path).as_posix()}"
                _add_file(zf, src, arcname)
    return dest


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: dist/)")
    ap.add_argument("--clean", action="store_true", help="remove the output directory first")
    args = ap.parse_args(argv)

    out_dir: Path = args.out
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cat = load_catalog()
    skills = sorted(cat.skills, key=lambda s: s.name)

    entries = []
    for skill in skills:
        dest = write_skill_zip(skill, out_dir)
        entries.append(
            {
                "name": skill.name,
                "layer": skill.layer,
                "dependencies": skill.dependencies,
                "file": dest.name,
                "sha256": sha256_of(dest),
                "size": dest.stat().st_size,
            }
        )
        print(f"wrote {dest.relative_to(REPO_ROOT) if dest.is_relative_to(REPO_ROOT) else dest}")

    bundle = write_bundle_zip(skills, out_dir)
    print(f"wrote {bundle.relative_to(REPO_ROOT) if bundle.is_relative_to(REPO_ROOT) else bundle}")

    manifest = {
        "bundle": {"file": bundle.name, "sha256": sha256_of(bundle), "size": bundle.stat().st_size},
        "skills": entries,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    sums = [f"{e['sha256']}  {e['file']}" for e in entries]
    sums.append(f"{manifest['bundle']['sha256']}  {bundle.name}")
    (out_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    print(f"packaged {len(entries)} skills + bundle into {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
