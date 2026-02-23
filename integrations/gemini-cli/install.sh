#!/usr/bin/env bash
set -euo pipefail
gemini mcp add zulipchat uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --scope user
