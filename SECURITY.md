# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow responsible disclosure:

1. **Do not** open a public GitHub issue
2. Email security concerns to: a.kougkas@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Resolution target**: Within 30 days for critical issues

## Scope

Security issues we're interested in:
- Authentication/authorization bypasses
- Credential exposure
- Remote code execution
- Data leakage

Out of scope:
- Issues in dependencies (report to upstream)
- Social engineering
- Physical attacks

## Security Best Practices

When using ZulipChat MCP:

- **Never commit credentials** - Use environment variables or zuliprc files
- **Use `--unsafe` flag carefully** - It enables administrative tools
- **Review bot permissions** - Grant minimum required Zulip permissions
- **Keep updated** - Security fixes are only applied to latest version

## Acknowledgments

We thank security researchers who responsibly disclose vulnerabilities.
