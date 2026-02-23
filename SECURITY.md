# Security Policy

## Supported versions

| Version | Status |
| --- | --- |
| 0.6.x | Supported |
| < 0.6.0 | Security fixes are not guaranteed |

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

### Credential handling

- Credentials are read from `zuliprc` and/or environment variables.
- `.env` is loaded from current working directory only.
- Credentials are used only for authenticated Zulip API calls.
- Credentials are not intentionally transmitted to third-party endpoints by the server.

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
