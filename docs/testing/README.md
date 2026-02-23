# Testing Guide

## Standard commands

```bash
uv run pytest -q
uv run ruff check .
uv run black .
uv run mypy src
```

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
