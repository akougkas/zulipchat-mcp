"""Rewrite or check the skill copies under integrations/ and the pancode/ pack.

The packaged skills and the exporter are canonical. The pack at pancode/ is
the PanCode plugin export with the zuliprc path left for the server to expand:

    zulipchat-mcp-integrate export --client pancode --mode plugin \\
        --tool-profile full --zulip-config-file '~/.zuliprc' --output-dir pancode

    uv run python scripts/sync_integration_templates.py [--check] [--pack-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zulipchat_mcp.integrations.agent_package import pancode_plugin_files
from zulipchat_mcp.integrations.registry import _build_base_config
from zulipchat_mcp.skill_content import skill_files

ROOT = Path(__file__).resolve().parents[1]
PACK_ZULIPRC = "~/.zuliprc"


def expected_templates() -> dict[Path, str]:
    canonical = skill_files()
    return {
        path: canonical[f"{path.parent.name}/SKILL.md"]
        for path in sorted((ROOT / "integrations").rglob("skills/*/SKILL.md"))
    }


def expected_pack() -> dict[str, str]:
    base = _build_base_config(PACK_ZULIPRC, None, False, "full")
    return pancode_plugin_files(base)


def pack_problems(pack_dir: Path) -> list[tuple[str, str]]:
    """(problem, relative path) for each pack file that is stale, missing or extra."""
    expected = expected_pack()
    present = (
        {
            path.relative_to(pack_dir).as_posix()
            for path in pack_dir.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if pack_dir.is_dir()
        else set()
    )
    problems = [("extra", relative) for relative in sorted(present - set(expected))]
    for relative, content in sorted(expected.items()):
        path = pack_dir / relative
        if relative not in present:
            problems.append(("missing", relative))
        elif path.is_symlink() or path.read_bytes() != content.encode("utf-8"):
            problems.append(("stale", relative))
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pack-dir", type=Path, default=ROOT / "pancode")
    args = parser.parse_args()
    pack_dir = args.pack_dir.resolve()
    stale = [
        path
        for path, content in expected_templates().items()
        if path.read_text(encoding="utf-8") != content
    ]
    problems = pack_problems(pack_dir)
    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}")
        for problem, relative in problems:
            print(f"{problem}: {pack_dir / relative}")
        sys.exit(1 if stale or problems else 0)
    for path in stale:
        path.write_text(expected_templates()[path], encoding="utf-8")
        print(f"updated: {path.relative_to(ROOT)}")
    expected = expected_pack()
    for problem, relative in problems:
        path = pack_dir / relative
        if problem == "extra":
            path.unlink()
            print(f"removed: {path}")
        else:
            path.unlink(missing_ok=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected[relative].encode("utf-8"))
            print(f"updated: {path}")


if __name__ == "__main__":
    main()
