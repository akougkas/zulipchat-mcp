"""Network-free SDK admission and official rate-limit contract regressions."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import format_datetime
from unittest.mock import Mock, patch

import pytest
import requests
import zulip

from zulipchat_mcp.core import api_budget
from zulipchat_mcp.core.api_budget import (
    PoliteZulipClient,
    RequestBudget,
    principal_key,
    shared_budget,
)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.wall = 1_700_000_000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def wall_time(self):
        return self.wall + self.now

    def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay

    def budget(self):
        return RequestBudget(
            monotonic=self.monotonic, wall_time=self.wall_time, sleep=self.sleep
        )


def response(payload=None, *, status=200, headers=None):
    result = Mock(spec=requests.Response)
    result.status_code = status
    result.headers = headers or {}
    result.json.return_value = payload or {"result": "success"}
    return result


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def sdk_client(clock, monkeypatch):
    """Real SDK initialization/query logic, fake per-session transport only."""
    budget = clock.budget()
    monkeypatch.setattr(api_budget, "shared_budget", lambda *args: budget)
    fake_session = Mock(spec=requests.Session)
    fake_session.hooks = {"response": []}
    outcomes = [response({"result": "success", "zulip_version": "12.0"})]

    def request(*args, **kwargs):
        value = outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        for hook in fake_session.hooks["response"]:
            hook(value)
        return value

    fake_session.request.side_effect = request

    def ensure_session(self):
        self.session = fake_session

    monkeypatch.setattr(zulip.Client, "ensure_session", ensure_session)
    # Avoid all SDK credential/environment/config lookup in these unit tests.
    with patch.object(
        zulip.Client, "get_server_settings", return_value={"zulip_version": "12.0"}
    ):
        client = PoliteZulipClient(
            email="synthetic@example.invalid",
            api_key="synthetic-key",
            site="https://realm.invalid",
            config_file="/nonexistent-synthetic-zuliprc",
        )
    outcomes.clear()
    return client, fake_session, outcomes, budget


def test_principal_normalization_and_account_isolation():
    assert principal_key(
        "https://Realm.INVALID:443/api/", " User@EXAMPLE.invalid "
    ) == (
        "https://realm.invalid",
        "user@example.invalid",
    )
    first = shared_budget("https://budget-test.invalid", "user@example.invalid")
    assert first is shared_budget(
        "https://BUDGET-test.invalid/api/", "USER@example.invalid"
    )
    assert first is not shared_budget("https://other.invalid", "user@example.invalid")
    assert first is not shared_budget(
        "https://budget-test.invalid", "bot@example.invalid"
    )
    assert principal_key("https://realm.invalid/prefix/api/", "a@b")[0].endswith(
        "/prefix"
    )
    with pytest.raises(ValueError):
        principal_key("https://user:secret@realm.invalid", "user@example.invalid")


def test_spacing_and_deadline_are_bounded(clock):
    budget = clock.budget()
    assert budget.admit() is None
    assert budget.admit(timeout=0.25)["code"] == "RATE_LIMIT_HIT"
    assert clock.sleeps == []
    assert budget.admit(timeout=0.5) is None
    assert clock.sleeps == [0.5]


def test_json_cooldown_shared_and_not_shortened(clock):
    budget = clock.budget()
    budget.observe(response({"code": "RATE_LIMIT_HIT", "retry-after": 28.7068}))
    budget.observe(response({"code": "RATE_LIMIT_HIT", "retry-after": 1}))
    error = budget.admit()
    assert error["retry-after"] == pytest.approx(28.7068)
    assert error["retryable"] is True
    assert clock.sleeps == []
    clock.now = 28.7068
    assert budget.admit() is None


def test_largest_json_header_and_reset_delay_wins(clock):
    budget = clock.budget()
    budget.observe(
        response(
            {"code": "RATE_LIMIT_HIT", "retry-after": 2},
            status=429,
            headers={
                "Retry-After": "3",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(clock.wall + 8),
                "X-RateLimit-Limit": "200",
            },
        )
    )
    assert budget.admit()["retry-after"] == 8


def test_retry_after_http_date_and_non_json_429(clock):
    budget = clock.budget()
    deadline = format_datetime(
        datetime.fromtimestamp(clock.wall + 7, tz=timezone.utc), usegmt=True
    )
    reply = response(status=429, headers={"Retry-After": deadline})
    reply.json.side_effect = ValueError("not json")
    assert budget.observe(reply)["retry-after"] == 7
    assert budget.admit()["retry-after"] == 7


def test_remaining_limit_reset_shape_successful_requests(clock):
    budget = clock.budget()
    budget.observe(
        response(
            headers={
                "X-RateLimit-Remaining": "4",
                "X-RateLimit-Limit": "2",
                "X-RateLimit-Reset": str(clock.wall + 8),
            }
        )
    )
    assert budget.admit(timeout=2)["retry-after"] == 4
    clock.now = 8
    assert budget.admit() is None
    assert budget.admit() is None
    assert clock.sleeps == [0.5]


@pytest.mark.parametrize("bad", ["garbage", "nan", "inf", "-1", True])
def test_malformed_retry_values_do_not_bypass_safe_429_fallback(clock, bad):
    budget = clock.budget()
    budget.observe(response({"code": "RATE_LIMIT_HIT", "retry-after": bad}, status=429))
    assert budget.admit()["retry-after"] == 1


def test_thread_safe_single_admission_at_same_instant(clock):
    budget = clock.budget()
    barrier = threading.Barrier(8)

    def try_admit(_):
        barrier.wait()
        return budget.admit(timeout=0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(try_admit, range(8)))
    assert sum(item is None for item in results) == 1
    assert len(clock.sleeps) == 0


def test_response_cooldown_interrupts_spacing_wait(clock):
    budget = clock.budget()
    assert budget.admit() is None

    def during_sleep(delay):
        clock.sleep(delay)
        budget.observe(response({"code": "RATE_LIMIT_HIT", "retry-after": 6}))

    budget.sleep = during_sleep
    assert budget.admit()["retry-after"] == 6
    assert clock.sleeps == [0.5]


def test_sdk_all_query_methods_and_instance_local_hook(sdk_client):
    client, session, outcomes, budget = sdk_client
    outcomes.extend([response(), response(), response()])
    assert client.do_api_query({}, "v1/test", method="GET")["result"] == "success"
    assert client.call_endpoint(url="messages", method="POST")["result"] == "success"
    assert client.call_endpoint(url="events", method="DELETE")["result"] == "success"
    assert len(session.hooks["response"]) == 1
    assert budget.monotonic() == 1
    assert session.request.call_count == 3
    assert requests.Session().hooks["response"] == []


def test_sdk_cooldown_blocks_query_without_touching_transport(sdk_client):
    client, session, outcomes, _ = sdk_client
    outcomes.append(response({"code": "RATE_LIMIT_HIT", "retry-after": 15}))
    first = client.do_api_query({}, "v1/messages", method="POST")
    second = client.do_api_query({}, "v1/messages", method="POST")
    assert first["code"] == second["code"] == "RATE_LIMIT_HIT"
    assert second["retry-after"] == 15
    assert session.request.call_count == 1


def test_no_automatic_mutation_retry_on_503_or_connection_error(sdk_client):
    client, session, outcomes, _ = sdk_client
    outcomes.append(response({"result": "error"}, status=503))
    client.retry_on_errors = True
    assert client.do_api_query({}, "v1/messages", method="POST")["result"] == "error"
    outcomes.append(requests.exceptions.ConnectionError("synthetic"))
    with pytest.raises(requests.exceptions.ConnectionError):
        client.do_api_query({}, "v1/messages", method="POST")
    assert session.request.call_count == 2


def test_long_poll_timeout_is_one_launch_with_90_second_network_timeout(sdk_client):
    client, session, outcomes, budget = sdk_client
    outcomes.append(requests.exceptions.Timeout("synthetic long poll"))
    with pytest.raises(requests.exceptions.Timeout):
        client.get_events(queue_id="synthetic", last_event_id=-1)
    assert session.request.call_count == 1
    assert session.request.call_args.kwargs["timeout"] == 90
    assert budget.monotonic() == 0


def test_explicit_long_poll_timeout_is_preserved(sdk_client):
    client, session, outcomes, _ = sdk_client
    outcomes.append(response())
    client.do_api_query({}, "v1/events", method="GET", longpolling=True, timeout=7.5)
    assert session.request.call_args.kwargs["timeout"] == 7.5


def test_rate_limit_json_fields_preserved_with_maximum_delay(sdk_client):
    client, _, outcomes, _ = sdk_client
    outcomes.append(
        response(
            {
                "result": "error",
                "code": "RATE_LIMIT_HIT",
                "msg": "Specific upstream quota",
                "retry-after": 2,
                "extra": {"bucket": "messages"},
            },
            status=429,
            headers={"Retry-After": "9"},
        )
    )
    result = client.do_api_query({}, "v1/messages", method="POST")
    assert result["msg"] == "Specific upstream quota"
    assert result["extra"] == {"bucket": "messages"}
    assert result["code"] == "RATE_LIMIT_HIT"
    assert result["retry-after"] == 9 and result["retryable"] is True


def test_sdk_constructor_server_settings_uses_budget(clock, monkeypatch, tmp_path):
    budget = clock.budget()
    monkeypatch.setattr(api_budget, "shared_budget", lambda *args: budget)
    observed = []

    def fake_query(self, *args, **kwargs):
        observed.append(self._budget)
        return {"result": "success", "zulip_version": "12.0"}

    # Patch only the SDK network query, leaving the subclass constructor/query.
    monkeypatch.setattr(zulip.Client, "do_api_query", fake_query)
    client = PoliteZulipClient(
        email="synthetic@example.invalid",
        api_key="synthetic-key",
        site="https://realm.invalid",
        config_file=str(tmp_path / "nonexistent"),
    )
    assert observed == [budget]
    assert client.retry_on_errors is False
    assert budget.admit(timeout=0)["code"] == "RATE_LIMIT_HIT"
