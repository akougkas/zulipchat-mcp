#!/usr/bin/env bash
set -euo pipefail
gemini mcp add zulipchat uvx zulipchat-mcp@0.8.0 --zulip-config-file ~/.zuliprc --scope user
