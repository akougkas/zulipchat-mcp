"""Count upstream requests and verify snapshot freshness and account isolation."""

import concurrent.futures
import threading
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.core import snapshots
from zulipchat_mcp.core.snapshots import ReadSnapshots, invalidate_realm_snapshots


@pytest.fixture(autouse=True)
def reset_root(monkeypatch):
    monkeypatch.setattr(snapshots, "_root", None)


def test_repeated_reads_share_snapshot_and_return_independent_data():
    cache = ReadSnapshots("a", "https://a.example")
    upstream = MagicMock(return_value={"result": "success", "messages": [{"id": 1}]})
    first = cache.fetch({"anchor": "newest"}, upstream)
    first["messages"][0]["id"] = 999
    second = cache.fetch({"anchor": "newest"}, upstream)
    assert second["messages"][0]["id"] == 1
    assert second["_cache"]["hit"] is True
    assert first["_cache"]["snapshot_id"] == second["_cache"]["snapshot_id"]
    assert upstream.call_count == 1


def test_concurrent_identical_requests_make_one_upstream_call():
    cache = ReadSnapshots("a", "https://a.example")
    called = threading.Event()
    release = threading.Event()

    def load():
        called.set()
        assert release.wait(2)
        return {"result": "success", "messages": []}

    upstream = MagicMock(side_effect=load)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(cache.fetch, {"anchor": "newest"}, upstream) for _ in range(8)
        ]
        assert called.wait(1)
        release.set()
        results = [future.result(2) for future in futures]
    assert upstream.call_count == 1
    assert sum(result["_cache"]["hit"] for result in results) == 7


def test_expiry_force_refresh_and_api_errors_are_truthful(monkeypatch):
    cache = ReadSnapshots("a", "https://a.example")
    upstream = MagicMock(return_value={"result": "success", "messages": []})
    cache.fetch({}, upstream)
    clock = snapshots.time.monotonic()
    monkeypatch.setattr(snapshots.time, "monotonic", lambda: clock + 16)
    cache.fetch({}, upstream)
    cache.fetch({}, upstream, use_cache=False)
    assert upstream.call_count == 3
    upstream.return_value = {
        "result": "error",
        "code": "RATE_LIMIT_HIT",
        "retry-after": 30,
    }
    assert cache.fetch({"different": True}, upstream)["retry-after"] == 30
    assert cache.fetch({"different": True}, upstream)["result"] == "error"
    assert upstream.call_count == 5


def test_disk_snapshot_survives_restart_but_never_crosses_principals(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(snapshots, "_root", tmp_path)
    first = ReadSnapshots("principal-a", "https://a.example")
    upstream = MagicMock(return_value={"result": "success", "messages": [{"id": 1}]})
    first.fetch({}, upstream)
    restarted = ReadSnapshots("principal-a", "https://a.example")
    assert restarted.fetch({}, upstream)["_cache"]["hit"] is True
    other = ReadSnapshots("principal-b", "https://a.example")
    assert other.fetch({}, upstream)["_cache"]["hit"] is False
    assert upstream.call_count == 2
    assert first.path.stat().st_mode & 0o777 == 0o600


def test_realm_invalidation_expires_both_bot_and_user_windows_only_in_that_realm():
    caches = [
        ReadSnapshots("user", "a"),
        ReadSnapshots("bot", "a"),
        ReadSnapshots("user", "b"),
    ]
    loaders = [
        MagicMock(return_value={"result": "success", "messages": []}) for _ in caches
    ]
    for cache, loader in zip(caches, loaders, strict=True):
        cache.fetch({}, loader)
    invalidate_realm_snapshots("a")
    for cache, loader in zip(caches, loaders, strict=True):
        cache.fetch({}, loader)
    assert [loader.call_count for loader in loaders] == [2, 2, 1]


def test_invalidation_during_fetch_does_not_recache_old_window():
    cache = ReadSnapshots("a", "a")

    def load():
        cache.invalidate()
        return {"result": "success", "messages": []}

    upstream = MagicMock(side_effect=load)
    cache.fetch({}, upstream)
    cache.fetch({}, upstream)
    assert upstream.call_count == 2


def test_large_windows_are_not_retained_in_memory_or_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "_root", tmp_path)
    cache = ReadSnapshots("a", "a")
    upstream = MagicMock(return_value={"result": "success", "content": "x" * 524289})
    cache.fetch({}, upstream)
    cache.fetch({}, upstream)
    assert upstream.call_count == 2
    assert cache._memory.size() == 0


def test_corrupt_optional_cache_does_not_turn_delivered_send_into_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(snapshots, "_root", tmp_path)
    cache = ReadSnapshots("a", "a")
    cache.path.write_bytes(b"damaged SQLite")
    cache.invalidate()
    assert cache.path is None
    result = cache.fetch({}, lambda: {"result": "success", "messages": []})
    assert result["result"] == "success"
