# Privacy Policy

**Last updated:** November 2026

## Overview

ZulipChat MCP Server ("the Server") is an open-source Model Context Protocol server that enables AI assistants to interact with Zulip Chat workspaces. This privacy policy explains how the Server handles your data.

## Data Collection

**The Server does not collect any data.**

- No telemetry or analytics
- No usage tracking
- No error reporting to external services
- No data transmitted to the developers or any third parties

## Data Flow

The Server only communicates with:

1. **Your Zulip Instance**: Using credentials you provide (API key, email, site URL)
2. **Your AI Client**: The MCP client you use (Claude Desktop, Claude Code, Cursor, etc.)

All communication is direct between your machine and your Zulip server. No data passes through any intermediary services.

## Credential Handling

- Credentials are provided by you via configuration files (`~/.zuliprc`) or environment variables
- Credentials are only used to authenticate with your Zulip server
- Credentials are never logged, stored persistently by the Server, or transmitted elsewhere
- We recommend using Zulip bot accounts with appropriate permissions rather than personal accounts

## Local Storage

The Server may create local files for:

- **Read caches**: Recent Zulip API responses, kept for performance in `$XDG_STATE_HOME/zulipchat-mcp/accounts/<fingerprint>/cache` (normally under `~/.local/state/`). `--ephemeral-state` keeps them in memory instead.
- **Agent bridge state**: If you run `zulipchat-mcp-agents`, it keeps conversation bindings and a rolling inbox of messages sent to each agent bot in `$XDG_STATE_HOME/zulipchat-mcp/agents/`. Inbox messages are removed once handled and kept at most 30 days.
- **Log files**: If debug mode is enabled, logs are written locally and never transmitted

You can delete these files at any time without affecting the Server's core functionality.

## Third-Party Services

The Server does not integrate with any third-party analytics, advertising, or data collection services.

## Open Source

This Server is fully open source under the MIT License. You can audit the complete source code at:
https://github.com/PanStudio/zulipchat-mcp

## Children's Privacy

This Server is a developer tool and is not intended for use by children under 13.

## Changes to This Policy

We may update this policy as the Server evolves. Changes will be documented in the repository's commit history and release notes.

## Contact

For privacy concerns or questions:
- GitHub Issues: https://github.com/PanStudio/zulipchat-mcp/issues
- Private security reports: https://github.com/PanStudio/zulipchat-mcp/security/advisories/new
