#!/usr/bin/env bash
set -euo pipefail
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
