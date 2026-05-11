# Testing Guide

## Standard commands

```bash
uv run pytest -q
uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
uv run mypy src
```

## MCP startup smoke

Run this whenever a change touches dependencies, packaging, FastMCP server
construction, tool registration, background tasks, lifespan management, or CLI
startup:

```bash
uv build
scripts/pre_release_smoke.sh --version X.Y.Z --allow-dirty
```

The smoke script starts the MCP stdio server with fake credentials, runs
`ping`, lists tools, calls `server_info`, and repeats that check from the built
wheel installed into a temporary virtual environment. It should not contact a
real Zulip server.

## Coverage gate

- Coverage threshold is `60%` (configured in `pyproject.toml`).

## Fast local run

```bash
uv run pytest -q -m "not slow and not integration"
```

## Contract-only run note

Contract-only subsets can fail the global coverage gate. Use:

```bash
uv run pytest -q -k "contract_" --no-cov
```

for exploratory checks.

## Clean rebuild

```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```
