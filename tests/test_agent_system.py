"""Tests for the agent communication system."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.zulipchat_mcp.database import AgentDatabase
from src.zulipchat_mcp.models.agent import Agent, AgentType, InputRequest
from src.zulipchat_mcp.models.task import Task, TaskCompletion, TaskStatus


class TestAgentModels:
    """Test agent data models."""

    def test_agent_creation(self):
        """Test creating an Agent instance."""
        agent = Agent(
            name="Test Agent",
            type=AgentType.CLAUDE_CODE,
            stream_name="ai-agents/test-agent",
        )

        assert agent.name == "Test Agent"
        assert agent.type == AgentType.CLAUDE_CODE
        assert agent.stream_name == "ai-agents/test-agent"
        assert agent.is_private is True
        assert agent.id is not None

    def test_input_request_creation(self):
        """Test creating an InputRequest instance."""
        request = InputRequest(
            agent_id="test-agent-123",
            question="Which file should I modify?",
            context={"files": ["main.py", "utils.py"]},
            options=["main.py", "utils.py", "both"],
        )

        assert request.agent_id == "test-agent-123"
        assert request.question == "Which file should I modify?"
        assert request.options is not None
        assert len(request.options) == 3
        assert request.timeout_seconds == 300
        assert request.is_answered is False


class TestTaskModels:
    """Test task data models."""

    def test_task_creation(self):
        """Test creating a Task instance."""
        task = Task(
            agent_id="test-agent-123",
            name="Implement feature X",
            description="Add new functionality for X",
            subtasks=["Design API", "Write tests", "Update docs"],
        )

        assert task.agent_id == "test-agent-123"
        assert task.name == "Implement feature X"
        assert task.status == TaskStatus.PENDING
        assert len(task.subtasks) == 3
        assert task.id is not None

    def test_task_completion_creation(self):
        """Test creating a TaskCompletion instance."""
        completion = TaskCompletion(
            task_id="task-456",
            summary="Successfully implemented feature X",
            outputs={
                "files_created": ["feature_x.py"],
                "files_modified": ["main.py"],
            },
            metrics={"time_taken": "2 hours", "test_coverage": "95%"},
        )

        assert completion.task_id == "task-456"
        assert completion.summary == "Successfully implemented feature X"
        assert len(completion.outputs) == 2
        assert completion.metrics["test_coverage"] == "95%"


class TestAgentDatabase:
    """Test database operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_agents.db"
        return AgentDatabase(str(db_path))

    def test_register_agent(self, db):
        """Test registering an agent in the database."""
        agent_id = str(uuid4())
        success = db.register_agent(
            agent_id=agent_id,
            name="Test Agent",
            agent_type="claude_code",
            stream_name="test-stream",
        )

        assert success is True

        # Retrieve the agent
        agent = db.get_agent(agent_id)
        assert agent is not None
        assert agent["name"] == "Test Agent"
        assert agent["type"] == "claude_code"

    def test_create_task(self, db):
        """Test creating a task in the database."""
        agent_id = str(uuid4())
        task_id = str(uuid4())

        # Register agent first
        db.register_agent(
            agent_id=agent_id,
            name="Test Agent",
            agent_type="claude_code",
        )

        # Create task
        success = db.create_task(
            task_id=task_id,
            agent_id=agent_id,
            name="Test Task",
            description="Test task description",
        )

        assert success is True

        # Get active tasks
        tasks = db.get_active_tasks(agent_id)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Test Task"

    def test_update_task_progress(self, db):
        """Test updating task progress."""
        agent_id = str(uuid4())
        task_id = str(uuid4())

        # Setup
        db.register_agent(agent_id, "Test Agent", "claude_code")
        db.create_task(task_id, agent_id, "Test Task", "Description")

        # Update progress
        success = db.update_task_progress(
            task_id=task_id,
            progress_percentage=50,
            estimated_time="5 minutes",
        )

        assert success is True

    def test_complete_task(self, db):
        """Test completing a task."""
        agent_id = str(uuid4())
        task_id = str(uuid4())

        # Setup
        db.register_agent(agent_id, "Test Agent", "claude_code")
        db.create_task(task_id, agent_id, "Test Task", "Description")

        # Complete task
        success = db.complete_task(
            task_id=task_id,
            summary="Task completed successfully",
            outputs={"result": "success"},
            metrics={"duration": "10 minutes"},
        )

        assert success is True

        # Verify no active tasks
        tasks = db.get_active_tasks(agent_id)
        assert len(tasks) == 0

    def test_create_input_request(self, db):
        """Test creating an input request."""
        agent_id = str(uuid4())
        request_id = str(uuid4())

        # Register agent first
        db.register_agent(agent_id, "Test Agent", "claude_code")

        # Create input request
        success = db.create_input_request(
            request_id=request_id,
            agent_id=agent_id,
            question="Which option?",
            context={"info": "test"},
            options=["A", "B", "C"],
        )

        assert success is True

        # Get pending request
        request = db.get_pending_request(request_id)
        assert request is not None
        assert request["question"] == "Which option?"
        assert request["is_answered"] == 0

    def test_save_user_response(self, db):
        """Test saving a user response."""
        agent_id = str(uuid4())
        request_id = str(uuid4())

        # Setup
        db.register_agent(agent_id, "Test Agent", "claude_code")
        db.create_input_request(request_id, agent_id, "Question?", {"info": "test"})

        # Save response
        success = db.save_user_response(
            request_id=request_id,
            response="Option A",
            user_email="user@example.com",
        )

        assert success is True

        # Verify request is answered
        request = db.get_pending_request(request_id)
        assert request is None  # Should return None for answered requests


class TestAgentRegistry:
    """Test agent registry service."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Zulip client."""
        client = MagicMock()
        client.get_streams.return_value = []
        client.send_message.return_value = {"result": "success", "id": 123}
        client.client.add_subscriptions.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_config(self):
        """Create a mock config manager."""
        config = MagicMock()
        return config

    @patch("src.zulipchat_mcp.services.agent_registry.AgentDatabase")
    def test_register_agent(self, mock_db, mock_config, mock_client):
        """Test registering an agent through the registry."""
        from src.zulipchat_mcp.services.agent_registry import AgentRegistry

        # Setup mock database
        mock_db_instance = MagicMock()
        mock_db_instance.register_agent.return_value = True
        mock_db.return_value = mock_db_instance

        # Setup mock client to return success for stream creation
        mock_client.get_streams.return_value = []  # No existing streams
        mock_client.client.add_subscriptions.return_value = {"result": "success"}
        mock_client.send_message.return_value = {"result": "success", "id": 123}

        # Create registry
        registry = AgentRegistry(mock_config, mock_client)
        registry.db = mock_db_instance

        # Mock _create_agent_stream to return success
        registry._create_agent_stream = MagicMock(
            return_value={"success": True, "stream_id": 456}
        )

        # Register agent
        result = registry.register_agent(
            agent_name="Test Agent",
            agent_type="claude_code",
            private_stream=True,
        )

        assert result["status"] == "success"
        assert "agent" in result
        assert result["agent"]["name"] == "Test Agent"
