"""Exercise SEP-2640 on the wire and legacy resource compatibility."""

import hashlib

import pytest
import yaml
from fastmcp import Client, FastMCP
from starlette.testclient import TestClient

from tests.test_http_contract import rpc
from zulipchat_mcp.core.skills import register_skills


def test_modern_skill_discovery_manifest_and_direct_lookup():
    server = FastMCP("skills-contract", tasks=False)
    register_skills(server)
    with TestClient(server.http_app(json_response=True)) as client:
        discovered = rpc(client).json()["result"]
        assert (
            "io.modelcontextprotocol/skills" in discovered["capabilities"]["extensions"]
        )
        assert (
            rpc(client, "skills/get", {"uri": "skill://zulipchat/SKILL.md"}).json()[
                "result"
            ]["skill"]["frontmatter"]["name"]
            == "zulipchat"
        )
        listed = rpc(client, "skills/list").json()["result"]
        assert listed["resultType"] == "complete"
        assert listed["ttlMs"] == 300000
        assert listed["cacheScope"] == "public"
        assert len(listed["skills"]) == 4
        for entry in listed["skills"]:
            fetched = rpc(client, "skills/get", {"uri": entry["uri"]}).json()["result"]
            assert fetched["skill"] == entry
            assert fetched["ttlMs"] == listed["ttlMs"]
            assert fetched["cacheScope"] == listed["cacheScope"]
            resource = rpc(
                client,
                "resources/read",
                {"uri": entry["uri"]},
                {"Mcp-Name": entry["uri"]},
            ).json()["result"]
            content = resource["contents"][0]["text"]
            raw = content.encode("utf-8")
            assert entry["resources"][0]["size"] == len(raw)
            assert (
                entry["resources"][0]["digest"]
                == f"sha256:{hashlib.sha256(raw).hexdigest()}"
            )
            assert entry["frontmatter"] == yaml.safe_load(content.split("---", 2)[1])
        assert rpc(client, "tools/list").json()["result"]["tools"] == []


@pytest.mark.parametrize(
    "uri",
    ["file:///etc/passwd", "skill://../../etc/passwd", "skill://missing/SKILL.md"],
)
def test_skills_reject_unbundled_files_and_invalid_cursors(uri):
    server = FastMCP("skills-boundaries", tasks=False)
    register_skills(server)
    with TestClient(server.http_app(json_response=True)) as client:
        assert rpc(client, "skills/get", {"uri": uri}).json()["error"]["code"] == -32602
        assert (
            rpc(client, "skills/list", {"cursor": "unknown"}).json()["error"]["code"]
            == -32602
        )
        assert (
            "error"
            in rpc(client, "resources/read", {"uri": uri}, {"Mcp-Name": uri}).json()
        )


async def test_legacy_clients_can_read_packaged_skills_without_extension_support():
    server = FastMCP("legacy-skills", tasks=False)
    register_skills(server)
    async with Client(server, mode="legacy") as client:
        resources = await client.list_resources()
        assert len(resources) == 4
        content = await client.read_resource("skill://zulipchat/SKILL.md")
        assert "name: zulipchat\n" in content[0].text
