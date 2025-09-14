# Release Guide

This guide explains how to release new versions of zulipchat-mcp to PyPI.

## Prerequisites

1. **PyPI Account**: Register at [PyPI](https://pypi.org/account/register/)
2. **GitHub Trusted Publishing**: Set up in your GitHub repository (recommended)
3. **Maintainer Access**: You must be a maintainer of this repository

## Release Process

### 1. Prepare the Release

1. **Update Version Numbers**:
   ```bash
   # Update version in both files to match (e.g., "2.6.0")
   vim src/zulipchat_mcp/__init__.py
   vim pyproject.toml
   ```

2. **Update Documentation**:
   - Update `README.md` if there are new features or changes
   - Update `AGENTS.md` for development-related changes
   - Update `CLAUDE.md` for any new development commands

3. **Run Tests**:
   ```bash
   uv run pytest -q
   uv run ruff check .
   uv run black .
   uv run mypy src
   ```

4. **Test Local Build**:
   ```bash
   uv build
   # Check that dist/ contains both .tar.gz and .whl files
   ls -la dist/
   ```

5. **Test Installation from Build**:
   ```bash
   # Test local installation
   uvx --from ./dist/zulipchat_mcp-*.whl zulipchat-mcp --help
   ```

### 2. Create and Push Git Release

1. **Commit Changes**:
   ```bash
   git add .
   git commit -m "release: v2.6.0"
   git push origin main
   ```

2. **Create Git Tag**:
   ```bash
   git tag -a v2.6.0 -m "Version 2.6.0"
   git push origin v2.6.0
   ```

3. **Create GitHub Release**:
   - Go to https://github.com/akougkas/zulipchat-mcp/releases
   - Click "Create a new release"
   - Select the tag you just created (v2.6.0)
   - Add release title: "v2.6.0"
   - Add release notes describing changes
   - Click "Publish release"

### 3. Automated PyPI Publishing

The GitHub Actions workflow (`.github/workflows/publish.yml`) will automatically:

1. **Trigger on Release**: Starts when you publish a GitHub release
2. **Run Tests**: Ensures all tests pass
3. **Verify Version**: Checks that package version matches git tag
4. **Build Package**: Creates source and wheel distributions
5. **Publish to PyPI**: Uses GitHub's trusted publishing

### 4. Verify Release

1. **Check PyPI**: Visit https://pypi.org/project/zulipchat-mcp/
2. **Test Installation**:
   ```bash
   # Test PyPI installation
   uvx zulipchat-mcp --help

   # Test with a real Zulip instance
   uvx zulipchat-mcp --zulip-email bot@org.com --zulip-api-key KEY --zulip-site https://org.zulipchat.com
   ```

3. **Update README**: Remove "(once published)" notes from installation instructions

## Manual PyPI Publishing (Fallback)

If automated publishing fails, you can publish manually:

### Setup

1. **Install Build Tools**:
   ```bash
   pip install build twine
   ```

2. **Generate API Token**:
   - Go to https://pypi.org/manage/account/
   - Create an API token with scope "Entire account"
   - Save the token securely

### Manual Upload

1. **Build Package**:
   ```bash
   uv build
   ```

2. **Upload to TestPyPI** (recommended first):
   ```bash
   twine upload --repository testpypi dist/*
   # Username: __token__
   # Password: your-testpypi-api-token
   ```

3. **Test from TestPyPI**:
   ```bash
   uvx --index-url https://test.pypi.org/simple/ zulipchat-mcp --help
   ```

4. **Upload to PyPI**:
   ```bash
   twine upload dist/*
   # Username: __token__
   # Password: your-pypi-api-token
   ```

## Post-Release Tasks

1. **Announce Release**:
   - Update any documentation that references installation
   - Share on relevant channels/communities
   - Update any example configurations

2. **Monitor for Issues**:
   - Check GitHub Issues for installation problems
   - Monitor PyPI download stats
   - Test with different MCP clients

## Troubleshooting

### Version Mismatch Error
```
Version mismatch: tag=2.6.0, package=2.5.0
```
**Solution**: Update `src/zulipchat_mcp/__init__.py` to match the git tag.

### Build Failures
```
Error: No module named 'src'
```
**Solution**: Verify `pyproject.toml` has correct `[tool.hatch.build.targets.wheel]` configuration.

### Import Errors After Installation
```
ModuleNotFoundError: No module named 'zulipchat_mcp.server'
```
**Solution**: Check that entry points in `pyproject.toml` use correct module paths.

### PyPI Upload Permission Denied
**Solution**: Ensure you have maintainer access and are using correct API token.

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0): Breaking changes
- **Minor** (X.Y.0): New features, backwards compatible
- **Patch** (X.Y.Z): Bug fixes, backwards compatible

Examples:
- `2.5.0` → `2.5.1`: Bug fix release
- `2.5.0` → `2.6.0`: New features added
- `2.5.0` → `3.0.0`: Breaking changes