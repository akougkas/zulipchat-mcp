"""Task data models for agent task lifecycle management."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task being executed by an agent."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Represents a task being executed by an agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    subtasks: list[str] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output_summary: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    progress_percentage: int | None = None
    estimated_time: str | None = None
    blockers: list[str] | None = None
    zulip_topic: str | None = None

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class TaskUpdate(BaseModel):
    """Update to an existing task."""

    task_id: str
    subtask_completed: str | None = None
    progress_percentage: int | None = None
    blockers: list[str] | None = None
    status: TaskStatus | None = None
    estimated_time: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class TaskCompletion(BaseModel):
    """Task completion details."""

    task_id: str
    summary: str
    outputs: dict[str, Any]
    metrics: dict[str, Any] | None = None
    files_created: list[str] | None = None
    files_modified: list[str] | None = None
    tests_added: int | None = None
    test_status: str | None = None
    completed_at: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
