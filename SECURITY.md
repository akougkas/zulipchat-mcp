# Security Policy

## Supported versions

| Version | Status |
| --- | --- |
| Latest published stable release (currently 0.7.6) | Supported |
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

`--unsafe` must be explicitly enabled for guarded destructive flows. In current code, this includes destructive topic operations through `agents_channel_topic_ops`.

### Identity boundaries

- Default identity is user identity.
- Bot identity is optional and requires separate credentials.
- `switch_identity` fails for bot mode if bot credentials are missing.
- `agents_channel_topic_ops` is restricted to bot identity and `Agents-Channel`.
- A selected credential file supplies its email, API key, and site together.
  Clients and caches are isolated by configuration and identity. Restart the
  process after changing credential files.
- Environment bot credentials without a separately selected bot file use the
  selected user's effective realm. An ambient site cannot redirect that bot's key.
- Local session/request state is bound to the effective realms and principals.
  Default databases are account-scoped and explicit paths reject mismatches.
  Legacy database adoption requires a verified explicit path and operator
  association. All binding failures abort startup, including storage failures.
- Agent requests are bound to an owner and session topic. Approvals require
  `/approve REQUEST_ID` or `/deny REQUEST_ID`; terminal decisions are immutable.
  Polling timeouts leave requests pending. Claude hook permission deadlines deny
  on timeout. A Zulip approval does not override the coding host's permissions.

### Credential handling

- Credentials are read from `zuliprc` and/or environment variables.
- `.env` is loaded from current working directory only.
- Zulip credentials authenticate calls to the configured Zulip organization.
  File downloads validate their URL and destination before using credentials.
- Optional server-side LLM analytics send selected message data to Anthropic
  when `ANTHROPIC_API_KEY` is configured. Without that key, tools return raw data
  summaries for the calling agent to analyze.
- Run companion entrypoints through their actual distribution:
  `uvx --from zulipchat-mcp zulipchat-mcp-hook --help` (likewise `-setup` and
  `-integrate`). The companion command names are not separate PyPI packages.

### HTTP and local filesystem boundaries

- Streamable HTTP requires a Bearer token when binding beyond loopback. Host and
  Origin validation remain enabled; configure allowed public hostnames explicitly.
- Remote HTTP tools reject server-local file paths, event callbacks, and runtime
  identity switching. Stdio operations use the local operator's authorization.
- Task/session storage and listener cursors belong to one instance. Stateless HTTP
  transport does not make independent replicas interchangeable for these workflows.
- Exported skills are immutable packaged instructions. Their SHA-256 manifests
  verify content integrity; they do not establish publisher trust or grant access.
  Plugin and MCP execution trust belong to the host. Export refuses symlink paths
  and preflights all destination conflicts before writing.

### Validation and sanitization

- Message content is length-limited before send/edit operations.
- Tool inputs have explicit validation in core/user/search/topic/file paths.
- Agent reaction emoji is restricted to an approved registry.

### Rate limiting and retries

- The codebase includes rate-limiter and retry primitives (`core/error_handling.py`, `core/security.py`) used for controlled API behavior.
- Zulip server-side limits still apply.

## Operator guidance

- Keep `--unsafe` off unless needed.
- Use least-privilege bot accounts.
- Store `zuliprc` with restrictive file permissions.
- Rotate API keys regularly.
