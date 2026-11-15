"""Keep secret values out of text posted to Zulip for an agent.

Exact values the process can see are replaced wherever they appear; a few
unmistakable formats (private key blocks, common token prefixes, zuliprc key
lines) are replaced by shape. This is a net, not a guarantee.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_SECRET_NAME = re.compile(
    r"(?:^|_)(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)(?:_|$)", re.I
)
_SECRET_SHAPES = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
    r"|\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{30,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})",
    re.S,
)
_ZULIPRC_KEY = re.compile(r"(?im)^(\s*key\s*=\s*)\S{20,}\s*$")


def secret_values(
    *environments: Mapping[str, str], extra: Iterable[str | None] = ()
) -> list[str]:
    """Values of credential-named variables plus `extra`, longest first."""
    values = {
        value
        for environment in environments
        for name, value in environment.items()
        if _SECRET_NAME.search(name) and len(value) >= 12
    }
    values.update(value for value in extra if value)
    return sorted(values, key=len, reverse=True)


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[redacted]")
    text = _ZULIPRC_KEY.sub(r"\1[redacted]", text)
    return _SECRET_SHAPES.sub("[redacted]", text)
