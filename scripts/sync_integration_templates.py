"""Rewrite or check the skill copies checked in under integrations/.

The packaged skills are canonical.

    uv run python scripts/sync_integration_templates.py [--check]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zulipchat_mcp.skill_content import skill_files

ROOT = Path(__file__).resolve().parents[1]


def expected_templates() -> dict[Path, str]:
    canonical = skill_files()
    return {
        path: canonical[f"{path.parent.name}/SKILL.md"]
        for path in sorted((ROOT / "integrations").rglob("skills/*/SKILL.md"))
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = [
        path
        for path, content in expected_templates().items()
        if path.read_text(encoding="utf-8") != content
    ]
    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}")
        sys.exit(1 if stale else 0)
    for path in stale:
        path.write_text(expected_templates()[path], encoding="utf-8")
        print(f"updated: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
