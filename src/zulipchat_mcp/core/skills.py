"""Serve the packaged Agent Skills through Resources and SEP-2640."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

import yaml
from fastmcp import FastMCP
from fastmcp.server.extensions import MethodBinding, ServerExtension
from mcp.server.context import ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, RequestParams

from ..skill_content import skill_files


class ListSkillsParams(RequestParams):
    cursor: str | None = None


class GetSkillParams(RequestParams):
    uri: str


class SkillsExtension(ServerExtension):
    """Publish atomic skill entries with byte-exact integrity manifests."""

    identifier = "io.modelcontextprotocol/skills"

    def __init__(self) -> None:
        self.documents = skill_files()
        self.entries: dict[str, dict[str, Any]] = {}
        for relative, content in self.documents.items():
            frontmatter = yaml.safe_load(content.split("---", 2)[1])
            name = relative.split("/")[0]
            if not isinstance(frontmatter, dict) or frontmatter.get("name") != name:
                raise ValueError(f"Invalid bundled skill frontmatter: {relative}")
            if not frontmatter.get("description"):
                raise ValueError(f"Missing bundled skill description: {relative}")
            uri = f"skill://{relative}"
            raw = content.encode("utf-8")
            self.entries[uri] = {
                "uri": uri,
                "frontmatter": frontmatter,
                "resources": [
                    {
                        "uri": uri,
                        "digest": f"sha256:{hashlib.sha256(raw).hexdigest()}",
                        "size": len(raw),
                    }
                ],
            }

    def methods(self) -> Sequence[MethodBinding]:
        modern = frozenset({"2026-07-28"})
        return (
            MethodBinding("skills/list", ListSkillsParams, self._list, modern),
            MethodBinding("skills/get", GetSkillParams, self._get, modern),
        )

    async def _list(
        self, context: ServerRequestContext[Any, Any], params: ListSkillsParams
    ) -> dict[str, Any]:
        if params.cursor is not None:
            raise MCPError(INVALID_PARAMS, "Unknown skill cursor")
        return {
            "resultType": "complete",
            "skills": list(self.entries.values()),
            "ttlMs": 300000,
            "cacheScope": "public",
        }

    async def _get(
        self, context: ServerRequestContext[Any, Any], params: GetSkillParams
    ) -> dict[str, Any]:
        if params.uri not in self.entries:
            raise MCPError(INVALID_PARAMS, "Unknown skill URI")
        return {
            "resultType": "complete",
            "skill": self.entries[params.uri],
            "ttlMs": 300000,
            "cacheScope": "public",
        }


def _reader(content: str) -> Callable[[], str]:
    def read() -> str:
        return content

    return read


def register_skills(mcp: FastMCP[Any]) -> None:
    """Keep resource access available to legacy hosts without adding tools."""
    extension = SkillsExtension()
    for relative, content in extension.documents.items():
        entry = extension.entries[f"skill://{relative}"]
        mcp.resource(
            f"skill://{relative}",
            name=relative,
            mime_type="text/markdown",
            description=entry["frontmatter"]["description"],
        )(_reader(content))
    mcp.add_extension(extension)
