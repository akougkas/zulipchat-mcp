#!/usr/bin/env python3
"""Version bump script for ZulipChat MCP.

Updates version strings across maintained files and reports any missing patterns.
Usage: python scripts/bump_version.py [--dry-run] VERSION
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VersionUpdate:
    file_path: str
    pattern: str
    replacement_template: str


# Files containing version strings and their replacement patterns.
VERSION_UPDATES: list[VersionUpdate] = [
    VersionUpdate(
        "pyproject.toml",
        r'version = "[0-9]+\.[0-9]+\.[0-9]+"',
        'version = "{version}"',
    ),
    VersionUpdate(
        "src/zulipchat_mcp/__init__.py",
        r'__version__ = "[0-9]+\.[0-9]+\.[0-9]+"',
        '__version__ = "{version}"',
    ),
    VersionUpdate(
        "src/zulipchat_mcp/tools/system.py",
        r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        '"version": "{version}"',
    ),
    VersionUpdate(
        "tests/tools/test_system.py",
        r'result\["version"\] == "[0-9]+\.[0-9]+\.[0-9]+"',
        'result["version"] == "{version}"',
    ),
    VersionUpdate(
        "CLAUDE.md",
        r"## Current Status \(v[0-9]+\.[0-9]+\.[0-9]+\)",
        "## Current Status (v{version})",
    ),
    VersionUpdate(
        "CLAUDE.md",
        r"ZulipChat MCP Server v[0-9]+\.[0-9]+\.[0-9]+",
        "ZulipChat MCP Server v{version}",
    ),
    VersionUpdate(
        "AGENTS.md",
        r"## Current Status \(v[0-9]+\.[0-9]+\.[0-9]+\)",
        "## Current Status (v{version})",
    ),
    VersionUpdate(
        "ROADMAP.md",
        r"## v[0-9]+\.[0-9]+\.[0-9]+ \(Current\)",
        "## v{version} (Current)",
    ),
    VersionUpdate(
        "RELEASE.md",
        r"# ZulipChat MCP v[0-9]+\.[0-9]+\.[0-9]+",
        "# ZulipChat MCP v{version}",
    ),
    VersionUpdate(
        "server.json",
        r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        '"version": "{version}"',
    ),
]

MANUAL_FILES = [
    "CHANGELOG.md",
]


def validate_version(version: str) -> bool:
    """Validate version string is semver format."""
    return bool(re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version))


def update_file(
    filepath: Path, pattern: str, replacement: str, dry_run: bool = False
) -> tuple[bool, int]:
    """Update a single file with the new version.

    Returns:
        tuple: (success, replacement_count)
    """
    if not filepath.exists():
        print(f"  ERROR: File not found: {filepath}")
        return False, 0

    content = filepath.read_text()
    new_content, count = re.subn(pattern, replacement, content)
    if count == 0:
        print(f"  ERROR: Pattern not found in {filepath}")
        print(f"         Pattern: {pattern}")
        return False, 0

    if dry_run:
        print(f"  [DRY RUN] Would update: {filepath} ({count} replacement(s))")
    else:
        filepath.write_text(new_content)
        print(f"  Updated: {filepath} ({count} replacement(s))")

    return True, count


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bump version across ZulipChat MCP versioned files"
    )
    parser.add_argument("version", help="New version (e.g., 0.6.0)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    args = parser.parse_args()

    if not validate_version(args.version):
        print(f"ERROR: Invalid version format: {args.version}")
        print("Expected format: X.Y.Z (e.g., 0.6.0)")
        return 1

    root = Path(__file__).parent.parent
    version = args.version

    print(f"Bumping version to {version}")
    if args.dry_run:
        print("[DRY RUN MODE - no files will be changed]")
    print()

    success_count = 0
    error_count = 0

    for item in VERSION_UPDATES:
        filepath = root / item.file_path
        replacement = item.replacement_template.format(version=version)

        ok, _ = update_file(filepath, item.pattern, replacement, args.dry_run)
        if ok:
            success_count += 1
        else:
            error_count += 1

    for file_rel in MANUAL_FILES:
        filepath = root / file_rel
        if filepath.exists():
            print(f"  SKIPPED (manual): {filepath}")
            success_count += 1
        else:
            print(f"  ERROR: File not found: {filepath}")
            error_count += 1

    print()
    print(f"Summary: {success_count} files processed, {error_count} errors")

    expected = len(VERSION_UPDATES) + len(MANUAL_FILES)
    if success_count == expected:
        print(f"All {expected} version locations processed successfully!")
        return 0

    print(f"WARNING: Expected {expected} processed locations, got {success_count}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
