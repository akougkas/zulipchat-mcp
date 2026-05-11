# Release Runbook

This is the blocking release process for ZulipChat MCP. Follow it in order.
If any gate fails, fix the root cause and rerun the failed command plus the full
gate that contains it.

## Release Standard

- A release is not ready until the source tree, built wheel, and MCP stdio server
  all pass from a clean environment.
- Startup smoke tests must use fake credentials and must not contact a real Zulip
  server. Real Zulip testing is reserved for targeted manual checks of behavior
  that actually needs the Zulip API.
- Framework feature changes are release-risk changes. If a FastMCP constructor
  argument, tool registration option, optional dependency extra, background task,
  lifespan hook, or async/sync boundary changes, add or update a contract test and
  run the MCP stdio smoke.
- Do not publish from hope. The release artifact must be installed and exercised
  before tagging.

## One-Time Prerequisites

- [ ] PyPI trusted publisher configured for this repo
  - Owner: `akougkas`
  - Repository: `zulipchat-mcp`
  - Workflow: `publish.yml`
  - Environment: `pypi`
- [ ] GitHub environment `pypi` exists in repo settings.
- [ ] Branch protection requires CI before merge to `main`.
- [ ] Tag and release permissions are limited to maintainers.

## Failure Modes To Check Explicitly

These checks exist because v0.7.0 failed at startup even though simple
entrypoint checks could pass.

- Package extras match enabled framework features. For example, FastMCP task
  support requires `fastmcp[... ,tasks]` so the built wheel installs `pydocket`.
- Tool registration is tested with real `FastMCP`, not only mocks.
- Server startup is tested through MCP stdio with fake credentials, including
  `ping`, `list_tools`, and `server_info`.
- Background-task tools are async-safe and only long-running tools opt in.
- Background services start and stop through FastMCP lifespan, not import-time or
  process-lifetime side effects.

## Release Steps

### 1. Decide Version Number

Use semver:

- `PATCH` for bug fixes and documentation-only releases.
- `MINOR` for new tools, new features, or non-breaking behavior changes.
- `MAJOR` for breaking API or configuration changes.

### 2. Start From A Clean, Reproducible Environment

```bash
git status --short
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

If `/tmp` is full, clean stale user-owned scratch directories before running
wheel smoke tests. Do not delete system-owned paths.

### 3. Bump Version Strings

Preview first when practical:

```bash
uv run python scripts/bump_version.py --dry-run X.Y.Z
uv run python scripts/bump_version.py X.Y.Z
```

This updates scripted version locations. Manually audit Markdown and packaging
metadata for stale version references that are intentionally not scripted.

### 4. Update Release Notes

Update:

- `CHANGELOG.md`: new top section with date, user-visible fixes, and credits.
  This is the source of truth for release notes; the GitHub release itself is
  generated automatically with `gh release create --generate-notes`.
- Any user or integration docs affected by behavior, install commands, or tool
  counts.

For community-reported fixes, credit reporters and PR authors in both changelog
and issue or PR responses.

### 5. Run Source Quality Gates

```bash
uv sync
uv run pytest -q
uv run mypy src
uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
```

The full pytest command is the release gate because it enforces coverage. Use
`--no-cov` only for exploratory subsets, never as release evidence.

### 6. Run Artifact And MCP Startup Gates

```bash
uv run python scripts/release_preflight.py --version X.Y.Z --allow-dirty
uv build
scripts/pre_release_smoke.sh --version X.Y.Z --allow-dirty
uvx --from dist/zulipchat_mcp-X.Y.Z-py3-none-any.whl zulipchat-mcp --version
uv run python scripts/mcp_stdio_smoke.py --expected-version X.Y.Z -- uv run zulipchat-mcp
```

`scripts/pre_release_smoke.sh` also installs the built wheel into a temporary
venv and runs the MCP stdio smoke from that installed wheel. That is the check
that catches missing extras, broken tool registration, and startup-only failures.

Optional distribution smoke after a release candidate is pushed:

```bash
scripts/pre_release_smoke.sh --version X.Y.Z --with-git --git-ref main
```

Run TestPyPI only when a pre-release has actually been uploaded there:

```bash
scripts/pre_release_smoke.sh --version X.Y.Z --with-testpypi
```

### 7. Stage Intentionally And Commit

Generated artifacts must not be staged: `dist/`, `htmlcov/`, `.coverage*`, and
`coverage.xml`.

```bash
git diff --stat
git status --short
git add AGENTS.md CHANGELOG.md CLAUDE.md ROADMAP.md pyproject.toml \
  server.json uv.lock src/zulipchat_mcp tests scripts .github docs README.md \
  CONTRIBUTING.md RELEASING.md
git status --short
git commit -m "chore: bump version to X.Y.Z"
```

Adjust the commit message for patch releases that include fixes, for example
`fix: make FastMCP task support explicit`.

### 8. Run Post-Commit Preflight

```bash
uv run python scripts/release_preflight.py --version X.Y.Z
```

This must pass without `--allow-dirty`.

### 9. Push, Tag, And Create The Release

Prepare the exact commands, then run only after maintainer confirmation:

```bash
git push
git tag vX.Y.Z
git push --tags
gh release create vX.Y.Z \
  --title "vX.Y.Z - Short Description" \
  --generate-notes \
  --latest
```

`--generate-notes` builds the GitHub release body from merged PRs and commits
since the previous tag. The detailed user-facing changelog lives in
`CHANGELOG.md`. Publishing the GitHub release triggers
`.github/workflows/publish.yml`, which builds and uploads to PyPI through
trusted publisher OIDC.

### 10. Verify Published Artifacts

- [ ] GitHub release exists and is marked latest.
- [ ] Publish workflow completed successfully.
- [ ] PyPI shows the new version.
- [ ] Fresh install reports the new version:

```bash
uvx --refresh-package zulipchat-mcp zulipchat-mcp --version
```

- [ ] Fresh MCP stdio startup works from the published package:

```bash
uv run python scripts/mcp_stdio_smoke.py --expected-version X.Y.Z -- \
  uvx --refresh-package zulipchat-mcp zulipchat-mcp
```

Run this from the release commit checkout so the smoke script is available.

### 11. Notify Community

- Comment on fixed issues and addressed PRs.
- State the released version and upgrade command.
- Credit reporters and contributors.
- Do not claim the release is published until the GitHub release exists and the
  publish workflow has started or completed.

## Troubleshooting

**Preflight failed**

- Fix version alignment or missing release docs.
- Rerun `uv run python scripts/release_preflight.py --version X.Y.Z --allow-dirty`.

**MCP stdio smoke failed**

- Treat this as a release blocker.
- Inspect whether startup fails during configuration, FastMCP construction, tool
  registration, lifespan startup, or `server_info`.
- Common causes: missing dependency extras, sync functions registered as
  background tasks, bad type annotations, stdout pollution, or import-time side
  effects.

**Publish workflow failed**

- Check the Actions logs.
- If the tag or GitHub release is wrong, delete the remote tag and release,
  fix the release commit, retag, and recreate the release.

**PyPI trusted publisher is not configured**

- Prefer fixing trusted publisher configuration.
- Use manual upload only as a maintainer-approved fallback:

```bash
uv build
uv run twine upload dist/*
```
