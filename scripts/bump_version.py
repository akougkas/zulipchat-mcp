#!/usr/bin/env python3
"""Version bump script for ZulipChat MCP.

Updates version strings across all 12 files that contain version references.
Usage: python scripts/bump_version.py [--dry-run] VERSION
"""

import argparse
import re
import sys
from pathlib import Path

# All files containing version strings and their patterns
VERSION_FILES = [
    # (file_path, pattern, replacement_template)
    ("pyproject.toml", r'version = "[0-9]+\.[0-9]+\.[0-9]+"', 'version = "{version}"'),
    (
        "src/zulipchat_mcp/__init__.py",
        r'__version__ = "[0-9]+\.[0-9]+\.[0-9]+"',
        '__version__ = "{version}"',
    ),
    (
        "src/zulipchat_mcp/server.py",
        r'Registering v[0-9]+\.[0-9]+\.[0-9]+ tools',
        "Registering v{version} tools",
    ),
    (
        "src/zulipchat_mcp/tools/system.py",
        r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        '"version": "{version}"',
    ),
    (
        "tests/tools/test_system.py",
        r'result\["version"\] == "[0-9]+\.[0-9]+\.[0-9]+"',
        'result["version"] == "{version}"',
    ),
    (
        "CLAUDE.md",
        r"## Current Status \(v[0-9]+\.[0-9]+\.[0-9]+\)",
        "## Current Status (v{version})",
    ),
    (
        "CLAUDE.md",
        r"ZulipChat MCP Server v[0-9]+\.[0-9]+\.[0-9]+",
        "ZulipChat MCP Server v{version}",
    ),
    (
        "AGENTS.md",
        r"## Current Status \(v[0-9]+\.[0-9]+\.[0-9]+\)",
        "## Current Status (v{version})",
    ),
    (
        "CHANGELOG.md",
        r"## \[[0-9]+\.[0-9]+\.[0-9]+\] - [0-9]{4}-[0-9]{2}-[0-9]{2}",
        None,  # Special handling - add new section, don't replace
    ),
    (
        "ROADMAP.md",
        r"## v[0-9]+\.[0-9]+\.[0-9]+ \(Current\)",
        "## v{version} (Current)",
    ),
    (
        "docs/api-reference/system.md",
        r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        '"version": "{version}"',
    ),
    (
        "docs/user-guide/configuration.md",
        r"ZulipChat MCP v[0-9]+\.[0-9]+\.[0-9]+",
        "ZulipChat MCP v{version}",
    ),
    (
        "RELEASE.md",
        r"# ZulipChat MCP v[0-9]+\.[0-9]+\.[0-9]+",
        "# ZulipChat MCP v{version}",
    ),
]


def validate_version(version: str) -> bool:
    """Validate version string is semver format."""
    return bool(re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version))


def update_file(
    filepath: Path, pattern: str, replacement: str, dry_run: bool = False
) -> bool:
    """Update a single file with the new version.

    Returns True if file was updated (or would be), False if pattern not found.
    """
    if not filepath.exists():
        print(f"  ERROR: File not found: {filepath}")
        return False

    content = filepath.read_text()
    if not re.search(pattern, content):
        print(f"  ERROR: Pattern not found in {filepath}")
        print(f"         Pattern: {pattern}")
        return False

    new_content = re.sub(pattern, replacement, content)

    if dry_run:
        print(f"  [DRY RUN] Would update: {filepath}")
    else:
        filepath.write_text(new_content)
        print(f"  Updated: {filepath}")

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bump version across all ZulipChat MCP files"
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

    for file_rel, pattern, replacement_template in VERSION_FILES:
        filepath = root / file_rel

        # Special handling for CHANGELOG.md - skip if no replacement template
        if replacement_template is None:
            # For CHANGELOG, we just verify the file exists and has version entries
            if filepath.exists():
                print(f"  SKIPPED (manual): {filepath} - update changelog manually")
                success_count += 1
            else:
                print(f"  ERROR: File not found: {filepath}")
                error_count += 1
            continue

        replacement = replacement_template.format(version=version)

        if update_file(filepath, pattern, replacement, args.dry_run):
            success_count += 1
        else:
            error_count += 1

    print()
    print(f"Summary: {success_count} files updated, {error_count} errors")

    # We expect 12 files total (13 entries but CHANGELOG is manual)
    expected = len(VERSION_FILES)
    if success_count == expected:
        print(f"All {expected} version locations processed successfully!")
        return 0
    else:
        print(f"WARNING: Expected {expected} files, but processed {success_count}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
