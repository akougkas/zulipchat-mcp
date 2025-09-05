"""Agent data models for ZulipChat MCP Agent Communication System."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of AI agents that can register."""

    CLAUDE_CODE = "claude_code"
    GITHUB_COPILOT = "github_copilot"
    CODEIUM = "codeium"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Current status of an agent."""

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    OFFLINE = "offline"


class Agent(BaseModel):
    """Represents a registered AI agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    type: AgentType = AgentType.CLAUDE_CODE
    stream_id: int | None = None
    stream_name: str | None = None
    bot_email: str | None = None
    webhook_url: str | None = None
    is_private: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class AgentMessage(BaseModel):
    """Message sent from an agent to humans."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    message_type: str  # status, question, completion, error
    content: str
    metadata: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    zulip_message_id: int | None = None

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class UserResponse(BaseModel):
    """Response from a user to an agent's request."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    agent_id: str
    response: str
    selection: int | None = None  # For multiple choice
    responded_at: datetime = Field(default_factory=datetime.now)
    user_email: str | None = None

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class InputRequest(BaseModel):
    """Request for user input from an agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    options: list[str] | None = None
    timeout_seconds: int = 300
    requested_at: datetime = Field(default_factory=datetime.now)
    response: UserResponse | None = None
    is_answered: bool = False

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
