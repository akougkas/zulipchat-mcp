"""Principal-scoped Zulip request shaping without transparent network retries."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from typing import IO, Any
from urllib.parse import urlsplit, urlunsplit

import requests
import zulip


def principal_key(site: str, email: str) -> tuple[str, str]:
    """Normalize SDK base URLs and principals, excluding API keys entirely."""
    parsed = urlsplit(site if "://" in site else "https://" + site)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A valid Zulip realm is required")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Zulip realm must not contain user information")
    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port is not None and (parsed.scheme.lower(), port) not in {
        ("https", 443),
        ("http", 80),
    }:
        host += f":{port}"
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4]
    principal = email.strip().casefold()
    if not principal:
        raise ValueError("A Zulip principal is required")
    return urlunsplit((parsed.scheme.lower(), host, path, "", "")), principal


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def rate_limit_error(delay: float, message: str) -> dict[str, Any]:
    return {
        "result": "error",
        "code": "RATE_LIMIT_HIT",
        "msg": message,
        "retry-after": max(0.0, delay),
        "retryable": True,
    }


class RequestBudget:
    """One admission at a time; requests/long polls run outside the lock.

    Spacing waits have a deadline. Cooldowns reject immediately and never make
    a request or sleep until a potentially very distant server retry time.
    """

    def __init__(
        self,
        spacing: float = 0.5,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        wall_time: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not math.isfinite(spacing) or spacing <= 0:
            raise ValueError("Request spacing must be positive and finite")
        self.spacing = spacing
        self.monotonic = monotonic
        self.wall_time = wall_time
        self.sleep = sleep
        self._lock = threading.Lock()
        self._next_launch = 0.0
        self._cooldown_until = 0.0
        self._header_spacing = 0.0
        self._header_until = 0.0

    def admit(self, timeout: float = 2.0) -> dict[str, Any] | None:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Admission timeout must be nonnegative and finite")
        deadline = self.monotonic() + timeout
        while True:
            if not self._lock.acquire(timeout=max(0.0, deadline - self.monotonic())):
                return rate_limit_error(
                    self.spacing, "Zulip admission deadline reached"
                )
            try:
                now = self.monotonic()
                cooldown = self._cooldown_until - now
                if cooldown > 0:
                    return rate_limit_error(cooldown, "Zulip principal is cooling down")
                delay = self._next_launch - now
                if delay <= 0:
                    if now > deadline:
                        return rate_limit_error(
                            self.spacing, "Zulip admission deadline reached"
                        )
                    interval = max(
                        self.spacing,
                        self._header_spacing if now < self._header_until else 0.0,
                    )
                    self._next_launch = now + interval
                    return None
                if delay > max(0.0, deadline - now):
                    return rate_limit_error(delay, "Zulip admission deadline reached")
            finally:
                self._lock.release()
            # Never hold the admission lock while sleeping or doing network I/O.
            # A concurrent response hook may impose cooldown during this wait.
            self.sleep(delay)

    def observe(self, response: requests.Response) -> dict[str, Any] | None:
        """SDK-local response hook input: JSON plus official rate-limit headers."""
        try:
            payload = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        limited = response.status_code == 429 or payload.get("code") == "RATE_LIMIT_HIT"
        # requests uses case-insensitive headers; normalize also for test doubles.
        headers = {key.lower(): value for key, value in response.headers.items()}
        delays: list[float] = []
        retry = _number(headers.get("retry-after"))
        if retry is None and headers.get("retry-after"):
            try:
                retry = max(
                    0.0,
                    parsedate_to_datetime(headers["retry-after"]).timestamp()
                    - self.wall_time(),
                )
            except (ValueError, TypeError, OverflowError):
                pass
        if retry is not None:
            delays.append(retry)
        json_retry = _number(payload.get("retry-after"))
        if limited and json_retry is not None:
            delays.append(json_retry)
        remaining = _number(headers.get("x-ratelimit-remaining"))
        limit = _number(headers.get("x-ratelimit-limit"))
        reset = _number(headers.get("x-ratelimit-reset"))
        reset_delay = max(0.0, reset - self.wall_time()) if reset is not None else None
        if remaining == 0:
            delays.append(reset_delay if reset_delay is not None else 1.0)
        if limited and not delays:
            delays.append(1.0)
        delay = max(delays, default=0.0)
        now = self.monotonic()
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, now + delay)
            effective_delay = max(0.0, self._cooldown_until - now)
            if remaining is not None and remaining > 0 and reset_delay:
                allowance = min(remaining, limit) if limit else remaining
                self._header_spacing = reset_delay / allowance
                self._header_until = now + reset_delay
                # This response also governs the next, already scheduled launch.
                self._next_launch = max(
                    self._next_launch, now + max(self.spacing, self._header_spacing)
                )
        if not limited:
            return None
        error = dict(payload)
        error.setdefault("result", "error")
        error.setdefault("code", "RATE_LIMIT_HIT")
        error.setdefault("msg", "Zulip API usage exceeded rate limit")
        error["retry-after"] = effective_delay
        error["retryable"] = True
        return error


_BUDGETS: dict[tuple[str, str], RequestBudget] = {}
_BUDGETS_LOCK = threading.Lock()


def shared_budget(site: str, email: str) -> RequestBudget:
    key = principal_key(site, email)
    with _BUDGETS_LOCK:
        if key not in _BUDGETS:
            _BUDGETS[key] = RequestBudget()
        return _BUDGETS[key]


class PoliteZulipClient(zulip.Client):
    """Drop-in SDK client: every query is admitted once, never retried here.

    retry_on_errors remains accepted for signature compatibility but is disabled
    deliberately, including after construction. Long polls get the SDK's 90s
    timeout while avoiding its unconditional timeout-retry loop. Admission waits
    are bounded independently of the network timeout.
    """

    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        config_file: str | None = None,
        verbose: bool = False,
        retry_on_errors: bool = True,
        site: str | None = None,
        client: str | None = None,
        cert_bundle: str | None = None,
        insecure: bool | None = None,
        client_cert: str | None = None,
        client_cert_key: str | None = None,
    ) -> None:
        self._budget: RequestBudget | None = None
        self._response_state = threading.local()
        self.admission_timeout = 2.0
        super().__init__(
            email=email,
            api_key=api_key,
            config_file=config_file,
            verbose=verbose,
            retry_on_errors=False,
            site=site,
            client=client,
            cert_bundle=cert_bundle,
            insecure=insecure,
            client_cert=client_cert,
            client_cert_key=client_cert_key,
        )

    def ensure_session(self) -> None:
        super().ensure_session()
        assert self.session is not None
        hooks = self.session.hooks.setdefault("response", [])
        if self._observe_response not in hooks:
            hooks.append(self._observe_response)

    def _observe_response(
        self, response: requests.Response, **kwargs: Any
    ) -> requests.Response:
        assert self._budget is not None
        self._response_state.error = self._budget.observe(response)
        return response

    def do_api_query(
        self,
        orig_request: Mapping[str, Any],
        url: str,
        method: str = "POST",
        longpolling: bool = False,
        files: list[IO[Any]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if self._budget is None:
            self._budget = shared_budget(self.base_url, self.email)
        error = self._budget.admit(self.admission_timeout)
        if error is not None:
            return error
        self._response_state.error = None
        self.retry_on_errors = False
        result = super().do_api_query(
            orig_request,
            url,
            method=method,
            longpolling=False,
            files=files,
            timeout=(90.0 if timeout is None else timeout) if longpolling else timeout,
        )
        return self._response_state.error or result
