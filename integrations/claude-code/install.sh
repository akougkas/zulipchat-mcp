#!/usr/bin/env bash
set -euo pipefail

ZULIP_CONFIG_FILE="${ZULIP_CONFIG_FILE:-$HOME/.zuliprc}"
PROJECT_DIR="${1:-$PWD}"

BOT_ARGS=()
if [[ -n "${ZULIP_BOT_CONFIG_FILE:-}" ]]; then
  BOT_ARGS=(--zulip-bot-config-file "$ZULIP_BOT_CONFIG_FILE")
elif [[ -f "$HOME/.zuliprc-bot" ]]; then
  BOT_ARGS=(--zulip-bot-config-file "$HOME/.zuliprc-bot")
fi

echo "User zuliprc: $ZULIP_CONFIG_FILE"
echo "Bot zuliprc: ${BOT_ARGS[1]:-none}"

# The export writes .mcp.json and the zulipchat skill into the project, both
# pinned to this version. It does not also register the server with
# `claude mcp add`: that would declare it twice.
uvx --from zulipchat-mcp==0.8.2 zulipchat-mcp-integrate export \
  --client claude-code \
  --mode standalone \
  --output-dir "$PROJECT_DIR" \
  --zulip-config-file "$ZULIP_CONFIG_FILE" \
  "${BOT_ARGS[@]}"
