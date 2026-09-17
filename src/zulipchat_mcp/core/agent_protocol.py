"""Shared agent session helpers for Zulip-controlled workflows."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TOPIC_PREFIX = "Agents/Session"
LIFECYCLE_EVENTS = {"started", "blocked", "waiting", "completed", "failed"}
APPROVE_WORDS = {"approve", "/approve", "approved", "yes", "y"}
DENY_WORDS = {"deny", "/deny", "denied", "no", "n"}


def normalize_slug(value: str, fallback: str = "session") -> str:
    """Normalize arbitrary text into a stable slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or fallback


def project_name_from_dir(path: str | None) -> str:
    """Resolve a project label from a filesystem path."""
    if not path:
        return "project"
    try:
        return normalize_slug(Path(path).name, fallback="project")
    except Exception:
        return "project"


def make_agent_id(owner_email: str, agent_type: str, agent_name: str) -> str:
    """Create a deterministic agent identifier."""
    seed = f"{owner_email.lower()}::{agent_type.lower()}::{agent_name.lower()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def make_session_id(agent_id: str, external_session_id: str | None = None) -> str:
    """Create a deterministic session identifier when an external ID exists."""
    seed = external_session_id or str(uuid.uuid4())
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{agent_id}::{seed}"))


def make_session_topic(
    project_name: str,
    agent_name: str,
    external_session_id: str | None = None,
    topic_prefix: str = DEFAULT_TOPIC_PREFIX,
) -> str:
    """Build the canonical Zulip topic for an agent session."""
    project_slug = normalize_slug(project_name, fallback="project")
    agent_slug = normalize_slug(agent_name, fallback="agent")
    if external_session_id:
        session_slug = normalize_slug(external_session_id, fallback="session")[:24]
        if session_slug != external_session_id:
            suffix = uuid.uuid5(uuid.NAMESPACE_URL, external_session_id).hex[:10]
            session_slug = f"{session_slug[:13]}-{suffix}"
    else:
        session_slug = str(uuid.uuid4())[:8]
    topic = f"{topic_prefix}/{project_slug}/{agent_slug}/{session_slug}"
    if len(topic) > 60:
        suffix = uuid.uuid5(uuid.NAMESPACE_URL, topic).hex[:16]
        topic = f"{topic[:43]}/{suffix}"
    return topic


def strip_message_markup(content: str) -> str:
    """Best-effort cleanup for Zulip-rendered content."""
    without_tags = re.sub(r"<[^>]+>", " ", content or "")
    without_entities = without_tags.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(without_entities.split()).strip()


@dataclass(frozen=True)
class ParsedControlMessage:
    """Parsed semantic classification for a Zulip topic message."""

    event_type: str
    normalized_content: str
    command: str | None = None
    arguments: str | None = None
    decision: str | None = None
    request_id: str | None = None


def parse_control_message(content: str) -> ParsedControlMessage:
    """Parse an incoming topic message into control semantics."""
    text = strip_message_markup(content)
    normalized = " ".join(text.lower().split())

    # Approval commands must be a complete command, never an embedded quote or
    # an arbitrary sentence. Preserve the case of IDs and steering arguments.
    approval = re.fullmatch(
        r"/?(approve|approved|yes|y|deny|denied|no|n)(?:\s+(?:ID:\s*)?([A-Za-z0-9_-]{4,}))?",
        text,
        flags=re.IGNORECASE,
    )
    if approval:
        return ParsedControlMessage(
            event_type="approval_response",
            normalized_content=normalized,
            decision="approve" if approval[1].lower() in APPROVE_WORDS else "deny",
            request_id=approval[2],
        )

    if normalized in APPROVE_WORDS:
        return ParsedControlMessage(
            event_type="approval_response",
            normalized_content=normalized,
            decision="approve",
        )

    if normalized in DENY_WORDS:
        return ParsedControlMessage(
            event_type="approval_response",
            normalized_content=normalized,
            decision="deny",
        )

    if normalized.startswith("/"):
        body = text[1:]
        command, _, arguments = body.partition(" ")
        return ParsedControlMessage(
            event_type="command",
            normalized_content=normalized,
            command=command.lower() or None,
            arguments=arguments or None,
        )

    return ParsedControlMessage(
        event_type="steer",
        normalized_content=normalized,
        arguments=text,
    )


def format_session_message(
    category: str, content: str, request_id: str | None = None
) -> str:
    """Format outbound session messages consistently."""
    clean_content = content.strip()
    if category in LIFECYCLE_EVENTS:
        heading = category.capitalize()
        if clean_content:
            return f"**{heading}**\n\n{clean_content}"
        return f"**{heading}**"

    if category == "approval_request":
        parts = ["**Approval Required**"]
        if request_id:
            parts[0] += f" (ID: {request_id})"
        if clean_content:
            parts.append(clean_content)
        if request_id:
            parts.append(
                f"Reply with `/approve {request_id}` or `/deny {request_id}` in this topic."
            )
        return "\n\n".join(parts)

    if category == "question":
        parts = ["**Input Requested**"]
        if request_id:
            parts[0] += f" (ID: {request_id})"
        if clean_content:
            parts.append(clean_content)
        return "\n\n".join(parts)

    return clean_content
