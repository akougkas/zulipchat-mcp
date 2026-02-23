# Contributing to ZulipChat MCP

Thanks for contributing. This guide is optimized for fast, low-friction contributions.

## Development setup

```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync
```

Run locally:

```bash
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Quality gates

Run before opening a PR:

```bash
uv run pytest -q
uv run ruff check .
uv run black .
uv run mypy src
```

Coverage gate is `60%`.

## Project layout

```text
src/zulipchat_mcp/
├── core/
├── tools/
├── services/
├── integrations/
├── utils/
├── config.py
├── server.py
└── setup_wizard.py
```

## Contribution rules

- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
- Keep changes focused and reviewable.
- Update docs when behavior or commands change.
- Do not commit secrets.

## Pull request checklist

- [ ] Problem and solution are clearly stated
- [ ] Tests and checks pass locally
- [ ] Docs are updated when needed
- [ ] No credentials or private data in commits

## Community workflow

- Triage labels: `bug`, `enhancement`, `good first issue`, `help wanted`, `community`, `needs-triage`
- Prefer merging community fixes instead of reimplementing in parallel.
- After release, comment on fixed issues with the released version.

## Where to ask questions

- [SUPPORT.md](SUPPORT.md)
- GitHub Discussions
- GitHub Issues
