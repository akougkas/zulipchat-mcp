#!/usr/bin/env python3
"""Automated preflight checklist for ZulipChat MCP releases.

Usage:
  uv run python scripts/release_preflight.py --version X.Y.Z
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    """Result for a single preflight check."""

    name: str
    passed: bool
    detail: str


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a file."""
    return path.read_text(encoding="utf-8")


def _extract_first(pattern: str, text: str) -> str | None:
    """Extract the first regex capture group."""
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1)


def _run_git(args: list[str]) -> str:
    """Run a git command and return stdout as stripped text."""
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _check_semver(version: str) -> CheckResult:
    passed = bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version))
    detail = version if passed else "Expected format MAJOR.MINOR.PATCH"
    return CheckResult("Version is valid semver", passed, detail)


def _check_pyproject_version(version: str) -> CheckResult:
    content = _read_text(ROOT / "pyproject.toml")
    actual = _extract_first(r'^version = "([^"]+)"', content)
    passed = actual == version
    detail = f"pyproject.toml version={actual!r}"
    return CheckResult("pyproject.toml version matches", passed, detail)


def _check_init_version(version: str) -> CheckResult:
    content = _read_text(ROOT / "src/zulipchat_mcp/__init__.py")
    actual = _extract_first(r'^__version__ = "([^"]+)"', content)
    passed = actual == version
    detail = f"src/zulipchat_mcp/__init__.py __version__={actual!r}"
    return CheckResult("__init__.py version matches", passed, detail)


def _check_system_tool_version(version: str) -> CheckResult:
    content = _read_text(ROOT / "src/zulipchat_mcp/tools/system.py")
    found = bool(re.search(rf'"version"\s*:\s*"{re.escape(version)}"', content))
    detail = (
        "server_info payload contains expected version"
        if found
        else "server_info payload missing expected version"
    )
    return CheckResult("system.py version matches", found, detail)


def _check_server_json(version: str) -> list[CheckResult]:
    payload = json.loads(_read_text(ROOT / "server.json"))
    top = payload.get("version")
    packages = payload.get("packages", [])
    package_versions = sorted(
        {pkg.get("version") for pkg in packages if pkg.get("version") is not None}
    )

    top_ok = top == version
    package_ok = package_versions == [version]

    return [
        CheckResult(
            "server.json top-level version matches",
            top_ok,
            f"server.json version={top!r}",
        ),
        CheckResult(
            "server.json package versions match",
            package_ok,
            f"server.json package versions={package_versions!r}",
        ),
    ]


def _check_changelog(version: str) -> CheckResult:
    content = _read_text(ROOT / "CHANGELOG.md")
    patterns = [
        rf"^## \[{re.escape(version)}\](?:\s|-|$)",
        rf"^## {re.escape(version)}\b",
        rf"^## v{re.escape(version)}\b",
    ]
    found = any(re.search(pattern, content, flags=re.MULTILINE) for pattern in patterns)
    detail = (
        f"CHANGELOG.md section for {version}" if found else "Missing changelog section"
    )
    return CheckResult("CHANGELOG entry exists", found, detail)


def _check_release_md(version: str) -> CheckResult:
    release_file = ROOT / "RELEASE.md"
    if not release_file.exists():
        return CheckResult("RELEASE.md exists", False, "Missing RELEASE.md")

    content = _read_text(release_file)
    found = bool(re.search(rf"^# .*v{re.escape(version)}\b", content, re.MULTILINE))
    detail = (
        "RELEASE.md title includes version"
        if found
        else "RELEASE.md title is not updated"
    )
    return CheckResult("RELEASE.md updated", found, detail)


def _check_required_scripts() -> CheckResult:
    content = _read_text(ROOT / "pyproject.toml")
    expected = ["zulipchat-mcp", "zulipchat-mcp-setup", "zulipchat-mcp-integrate"]
    missing = [name for name in expected if f"{name} =" not in content]
    passed = not missing
    detail = (
        "all expected entrypoints found" if passed else f"missing: {', '.join(missing)}"
    )
    return CheckResult("CLI entrypoints declared", passed, detail)


def _check_git_clean() -> CheckResult:
    status = _run_git(["status", "--porcelain"])
    passed = status == ""
    detail = (
        "working tree is clean" if passed else "working tree has uncommitted changes"
    )
    return CheckResult("Git working tree is clean", passed, detail)


def _check_tag_absent(version: str) -> CheckResult:
    tag = f"v{version}"
    existing = _run_git(["tag", "--list", tag])
    passed = existing == ""
    detail = "tag is available" if passed else f"tag {tag} already exists locally"
    return CheckResult(f"Git tag {tag} is available", passed, detail)


def _format_result(result: CheckResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    return f"[{status}] {result.name}: {result.detail}"


def main() -> None:
    """Run release preflight checks."""
    parser = argparse.ArgumentParser(
        description="Run automated release preflight checks before tagging."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Target release version (e.g. 0.6.0)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Skip failure on dirty git working tree.",
    )
    parser.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Skip failure if git tag vX.Y.Z already exists.",
    )
    parser.add_argument(
        "--skip-release-md",
        action="store_true",
        help="Skip checking RELEASE.md title version.",
    )
    args = parser.parse_args()

    results: list[CheckResult] = []
    results.append(_check_semver(args.version))
    results.append(_check_pyproject_version(args.version))
    results.append(_check_init_version(args.version))
    results.append(_check_system_tool_version(args.version))
    results.extend(_check_server_json(args.version))
    results.append(_check_changelog(args.version))
    if not args.skip_release_md:
        results.append(_check_release_md(args.version))
    results.append(_check_required_scripts())

    if args.allow_dirty:
        results.append(
            CheckResult(
                "Git working tree is clean",
                True,
                "skipped (--allow-dirty)",
            )
        )
    else:
        results.append(_check_git_clean())

    if args.allow_existing_tag:
        results.append(
            CheckResult(
                f"Git tag v{args.version} is available",
                True,
                "skipped (--allow-existing-tag)",
            )
        )
    else:
        results.append(_check_tag_absent(args.version))

    print(f"Release preflight for v{args.version}\n")
    for result in results:
        print(_format_result(result))

    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    print(f"\nSummary: {passed_count} passed, {failed_count} failed")

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
