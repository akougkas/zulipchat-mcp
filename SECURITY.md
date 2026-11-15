# Security Policy

## Supported versions

| Version | Status |
| --- | --- |
| Latest published stable release (currently 0.8.0) | Supported |
| Older releases | Upgrade to the latest stable release; fixes are not backported automatically |

## Responsible disclosure

Do not post vulnerabilities in public issues.

Report privately to: `a.kougkas@gmail.com`

Include:

- Impact
- Reproduction steps
- Affected version
- Suggested fix (optional)

Target response times:

- Acknowledgement: within 48 hours
- Initial assessment: within 7 days
- Critical fix target: within 30 days

## Security model

### Safe-by-default runtime

`zulipchat-mcp` starts in safe mode.

`--unsafe` must be explicitly enabled for guarded destructive flows. In current code, this is attachment deletion through `manage_files`.

### Identity boundaries

- Default identity is user identity.
- Bot identity is optional and requires separate credentials.
- `switch_identity` fails for bot mode if bot credentials are missing.
- A selected credential file supplies its email, API key, and site together.
  Clients and caches are isolated by configuration and identity. Restart the
  process after changing credential files.
- Environment bot credentials without a separately selected bot file use the
  selected user's effective realm. An ambient site cannot redirect that bot's key.
- Read caches are stored per account fingerprint (effective realms and
  principals), so a different account never reads another's cache. Account
  resolution failures abort startup.
- The MCP server cannot wake an agent and answers no request from Zulip. The
  agent bridge (`zulipchat-mcp-agents`) acts only on messages from the bot's
  owner in Zulip and the user IDs the agent file lists; everyone else is
  dropped without a reply. It pairs with the owner it first sees and stops
  serving if Zulip later reports another owner (`run --accept-owner` pairs
  again). Messages sent through this package's MCP server (Zulip client
  `zulipchat-mcp`) never prompt or answer an agent, so an agent that uses the
  owner's account through this server cannot drive another. Permission
  requests are answered only by typed messages, never by reactions, which
  carry no client name. Anything else that holds the owner's API key can still
  post as the owner. Do not give agents tools that act as the owner.
- The bridge redacts credential values and silences mentions in what it
  posts. By default it gives each agent only `ask_owner`
  (`zulip_tools = "ask"`). Bridged agents run with the local user's authority
  under their own permission policy. The bridge starts Clio at autonomy
  `default` and Claude in ACP mode `default` unless the agent file says
  otherwise, so both ask before acting; a permission request the owner leaves
  unanswered is denied.

### Credential handling

- Credentials are read from `zuliprc` and/or environment variables.
- A `.env` in the current working directory supplies only `ZULIP_EMAIL`,
  `ZULIP_API_KEY`, `ZULIP_SITE`, `ZULIP_BOT_EMAIL` and `ZULIP_BOT_API_KEY`, and
  only when the real environment sets none of that credential set. Every other
  key in it is ignored: hosts start the server inside the open project, so the
  file may belong to an untrusted checkout. The server reads no other state
  from the working directory.
- Zulip credentials authenticate calls to the configured Zulip organization.
  File downloads validate their URL and destination before using credentials.
- The server calls no LLM. Tools return Zulip data to the calling agent, which
  sends it to whatever model provider that agent uses.
- Run companion entrypoints through their actual distribution:
  `uvx --from zulipchat-mcp zulipchat-mcp-integrate --help` (likewise `-setup`
  and `-agents`). The companion command names are not separate PyPI packages.

### HTTP and local filesystem boundaries

- Streamable HTTP requires a Bearer token when binding beyond loopback. Host and
  Origin validation remain enabled; configure allowed public hostnames explicitly.
- Remote HTTP tools reject server-local file paths and runtime
  identity switching. Stdio operations use the local operator's authorization.
- Task storage and read caches are local to one machine. Stateless HTTP
  transport does not make independent replicas share them.
- Exported skills are immutable packaged instructions. Their SHA-256 manifests
  verify content integrity; they do not establish publisher trust or grant access.
  Plugin and MCP execution trust belong to the host. Export refuses symlink paths
  and preflights all destination conflicts before writing.

### Validation and sanitization

- Message content is length-limited before send/edit operations.
- Tool inputs have explicit validation in core/user/search/topic/file paths.
- Agent reaction emoji is restricted to an approved registry.

### Rate limiting and retries

- `core/api_budget.py` spaces requests per realm and principal and honors
  Zulip rate-limit cooldowns. It never retries a request transparently.
- Zulip server-side limits still apply.

## Operator guidance

- Keep `--unsafe` off unless needed.
- Use least-privilege bot accounts.
- Store `zuliprc` with restrictive file permissions.
- Rotate API keys regularly.
