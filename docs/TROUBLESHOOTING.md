# Troubleshooting

## Server fails with "Invalid configuration"

- Confirm `--zulip-config-file` points to an existing file.
- If omitted, verify one of these exists (a `zuliprc` in the working directory
  is not picked up):
  - `~/.zuliprc`
  - `~/.config/zulip/zuliprc`
- Or provide env fallback: `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.

## 401 Unauthorized

- Regenerate API key in Zulip personal settings.
- Ensure the key/email belongs to the same Zulip realm as `site`.
- Re-test by running setup wizard validation:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

## Bot identity cannot be selected

- Provide `--zulip-bot-config-file` or bot env credentials.
- Call `server_info` to confirm bot availability.

## Tool not found in client

- You are likely in core mode.
- Start with `--extended-tools` (or `ZULIPCHAT_EXTENDED_TOOLS=1`) for full tool set.

## Messages to an agent bot get no answer

- The MCP server cannot wake an agent. Zulip messages reach a coding agent only
  through the bridge; check it with `zulipchat-mcp-agents service status` and
  its log with `journalctl --user -u zulipchat-mcp-agents -f` (Linux). To run
  it in a terminal instead, stop the service first: a second process for the
  same bot exits with status 78 and "another process already serves this bot".
- The bridge hears only the bot's owner and the user IDs in the agent file's
  `allow`; everyone else is dropped without a reply.
- In a channel, mention the bot. See [Agent bots](integrations/agent-bots.md).
- A permission request is answered only by a message that is just `yes`, `ok`,
  `okay`, `approve`, `no` or `deny`, or by `/approve ID` and `/deny ID`.
  Reactions do not answer.

## An agent bot answers with the wrong model

- A conversation resumes the same agent session until you send `/new`, and a
  session keeps the model it started with. Send `/new` after changing the
  agent's model settings.

## Event queue errors

- Re-register using `register_events`.
- Validate `queue_id` and `last_event_id` sequence.

## File download/share failures

- Verify the file identifier is a valid upload path or full URL.
- Ensure the active identity has access to the underlying stream/DM context.

## HTTP transport returns 401 Unauthorized

- When binding `--transport http` beyond `127.0.0.1`, bearer token authentication is enabled.
- Ensure requests include `Authorization: Bearer <token>` matching `--auth-token` or `ZULIPCHAT_HTTP_AUTH_TOKEN`.

## Setup wizard EOF in non-interactive shells

The wizard is interactive. Run it directly in a terminal (no piped stdin):

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

## More help

- [Quick Start](user-guide/quick-start.md)
- [Configuration](user-guide/configuration.md)
- [Integration docs](integrations/README.md)
- [Support](../SUPPORT.md)
