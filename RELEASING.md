# Release Checklist

Step-by-step process for publishing a new version of ZulipChat MCP.
Follow in order — each step depends on the previous.

## Prerequisites (one-time setup)

- [ ] PyPI trusted publisher configured for this repo
  - Go to https://pypi.org/manage/project/zulipchat-mcp/settings/publishing/
  - Add GitHub as trusted publisher: owner `akougkas`, repo `zulipchat-mcp`, workflow `publish.yml`, environment `pypi`
- [ ] GitHub environment `pypi` created in repo settings (Settings → Environments → New)

## Release Steps

### 1. Decide version number

Follow semver: `MAJOR.MINOR.PATCH`
- **PATCH** (0.5.2 → 0.5.3): bug fixes, doc updates
- **MINOR** (0.5.3 → 0.6.0): new tools, new features, non-breaking changes
- **MAJOR** (0.6.0 → 1.0.0): breaking API changes

### 2. Bump version strings

```bash
uv run python scripts/bump_version.py X.Y.Z
```

This updates 12 files. Verify with `--dry-run` first if unsure.

### 3. Update CHANGELOG.md

Add a new section at the top of CHANGELOG.md:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Fixed
- ...

### Changed
- ...
```

### 4. Update RELEASE.md

Update the version in the title and the "What's New" section.

### 5. Run full quality checks

```bash
uv run pytest -q
uv run ruff check .
uv run black --check .
uv run mypy src
```

All must pass before proceeding.

### 6. Commit version bump

```bash
git add -A
git commit -m "chore: bump version to X.Y.Z"
```

### 7. Tag the release

```bash
git tag vX.Y.Z
git push && git push --tags
```

### 8. Create GitHub release

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z — Short Description" \
  --notes "$(cat <<'EOF'
### Added
- ...

### Fixed
- ...

**Full Changelog**: https://github.com/akougkas/zulipchat-mcp/compare/vPREV...vX.Y.Z
EOF
)" --latest
```

Publishing the release triggers `.github/workflows/publish.yml` which
automatically builds and uploads to PyPI via trusted publisher (OIDC).

### 9. Verify

- [ ] GitHub release shows as "Latest": https://github.com/akougkas/zulipchat-mcp/releases
- [ ] PyPI shows new version: https://pypi.org/project/zulipchat-mcp/
- [ ] Install works: `uvx zulipchat-mcp --version` (or equivalent check)
- [ ] CI passed on the release commit

### 10. Notify community (if applicable)

- Comment on any issues fixed in this release
- Credit community contributors in release notes and issue comments
- Respond to open PRs that were addressed

## Troubleshooting

**Publish workflow failed?**
- Check the Actions tab for error details
- Most common: version mismatch between tag and pyproject.toml
- Fix the issue, delete the tag, re-tag, and re-create the release

**Forgot to bump version before tagging?**
- Delete the tag: `git tag -d vX.Y.Z && git push --delete origin vX.Y.Z`
- Bump version, commit, re-tag, re-create release

**PyPI trusted publisher not configured?**
- Manual fallback: `uv build && uv run twine upload dist/*`
- Then set up trusted publisher for next time (see prerequisites)
