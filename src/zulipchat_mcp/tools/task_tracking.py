"""Task tracking tools for agent task lifecycle management."""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from ..client import ZulipClientWrapper
from ..config import ConfigManager
from ..database import AgentDatabase
from ..models.task import Task, TaskCompletion, TaskStatus
from ..services.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class TaskTracking:
    """Tools for managing agent task lifecycle."""

    def __init__(self, config: ConfigManager, client: ZulipClientWrapper):
        """Initialize task tracking tools."""
        self.config = config
        self.client = client
        db_url = getattr(config, "DATABASE_URL", "zulipchat_agents.db")
        self.db = AgentDatabase(db_url)
        self.registry = AgentRegistry(config, client)

    def start_task(
        self,
        agent_id: str,
        task_name: str,
        task_description: str,
        subtasks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Notify user that agent is starting a new task."""
        try:
            # Get agent details
            agent = self.registry.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Create task
            task_id = str(uuid4())
            task = Task(
                id=task_id,
                agent_id=agent_id,
                name=task_name,
                description=task_description,
                subtasks=subtasks,
                status=TaskStatus.ACTIVE,
                started_at=datetime.now(),
                zulip_topic=f"Task: {task_name}",
            )

            # Save to database
            success = self.db.create_task(
                task_id=task.id,
                agent_id=agent_id,
                name=task_name,
                description=task_description,
                subtasks=subtasks,
            )

            if not success:
                return {"status": "error", "error": "Failed to create task"}

            # Format and send notification
            content = self._format_task_start(task_name, task_description, subtasks)

            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic=task.zulip_topic,
                content=content,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "task_id": task_id,
                    "message": f"Task '{task_name}' started",
                }

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send notification"),
            }

        except Exception as e:
            logger.error(f"Failed to start task: {e}")
            return {"status": "error", "error": str(e)}

    def _format_task_start(
        self, name: str, description: str, subtasks: list[str] | None = None
    ) -> str:
        """Format task start notification."""
        content = f"🚀 **Task Started: {name}**\n\n"
        content += f"**Description:** {description}\n\n"

        if subtasks:
            content += "**Subtasks:**\n"
            for i, subtask in enumerate(subtasks, 1):
                content += f"{i}. ⬜ {subtask}\n"

        content += f"\n⏱️ **Started at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return content

    def update_task_progress(
        self,
        task_id: str,
        subtask_completed: str | None = None,
        progress_percentage: int | None = None,
        blockers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update task progress in real-time."""
        try:
            # Get task from database
            tasks = self.db.get_active_tasks()
            task = None
            for t in tasks:
                if t["id"] == task_id:
                    task = t
                    break

            if not task:
                return {"status": "error", "error": "Task not found or not active"}

            # Get agent for stream info
            agent = self.registry.get_agent(task["agent_id"])
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Update database
            self.db.update_task_progress(
                task_id=task_id,
                progress_percentage=progress_percentage,
                status="active",
            )

            # Format and send update
            content = self._format_task_update(
                subtask_completed, progress_percentage, blockers
            )

            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic=task.get("zulip_topic", f"Task: {task['name']}"),
                content=content,
            )

            if result.get("result") == "success":
                return {"status": "success", "message": "Task progress updated"}

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send update"),
            }

        except Exception as e:
            logger.error(f"Failed to update task progress: {e}")
            return {"status": "error", "error": str(e)}

    def _format_task_update(
        self,
        subtask_completed: str | None = None,
        progress_percentage: int | None = None,
        blockers: list[str] | None = None,
    ) -> str:
        """Format task progress update."""
        content = "📊 **Progress Update**\n\n"

        if subtask_completed:
            content += f"✅ Completed: {subtask_completed}\n\n"

        if progress_percentage is not None:
            # Create progress bar
            filled = int(progress_percentage / 10)
            empty = 10 - filled
            progress_bar = "█" * filled + "░" * empty
            content += f"**Progress:** {progress_bar} {progress_percentage}%\n\n"

        if blockers:
            content += "⚠️ **Blockers:**\n"
            for blocker in blockers:
                content += f"- {blocker}\n"

        return content

    def complete_task(
        self,
        task_id: str,
        summary: str,
        outputs: dict[str, Any],
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mark task as complete with detailed summary."""
        try:
            # Get task from database
            tasks = self.db.get_active_tasks()
            task = None
            for t in tasks:
                if t["id"] == task_id:
                    task = t
                    break

            if not task:
                return {"status": "error", "error": "Task not found or not active"}

            # Get agent for stream info
            agent = self.registry.get_agent(task["agent_id"])
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Update database
            success = self.db.complete_task(
                task_id=task_id,
                summary=summary,
                outputs=outputs,
                metrics=metrics,
            )

            if not success:
                return {"status": "error", "error": "Failed to complete task"}

            # Create completion object
            completion = TaskCompletion(
                task_id=task_id,
                summary=summary,
                outputs=outputs,
                metrics=metrics,
                files_created=outputs.get("files_created"),
                files_modified=outputs.get("files_modified"),
                tests_added=outputs.get("tests_added"),
                test_status=outputs.get("test_status"),
            )

            # Format and send completion notification
            content = self._format_task_completion(task["name"], completion)

            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic=task.get("zulip_topic", f"Task: {task['name']}"),
                content=content,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "message": f"Task '{task['name']}' completed",
                }

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send notification"),
            }

        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            return {"status": "error", "error": str(e)}

    def _format_task_completion(
        self, task_name: str, completion: TaskCompletion
    ) -> str:
        """Format task completion notification."""
        content = f"✅ **Task Completed: {task_name}**\n\n"
        content += f"**Summary:**\n{completion.summary}\n\n"

        if completion.files_created:
            content += f"📁 **Files Created:** {len(completion.files_created)}\n"
            for file in completion.files_created[:5]:  # Show first 5
                content += f"  • {file}\n"
            if len(completion.files_created) > 5:
                content += f"  • ... and {len(completion.files_created) - 5} more\n"
            content += "\n"

        if completion.files_modified:
            content += f"📝 **Files Modified:** {len(completion.files_modified)}\n"
            for file in completion.files_modified[:5]:  # Show first 5
                content += f"  • {file}\n"
            if len(completion.files_modified) > 5:
                content += f"  • ... and {len(completion.files_modified) - 5} more\n"
            content += "\n"

        if completion.tests_added:
            content += f"🧪 **Tests Added:** {completion.tests_added}\n"
            if completion.test_status:
                status_emoji = "✅" if completion.test_status == "passing" else "❌"
                content += f"**Test Status:** {status_emoji} {completion.test_status}\n"
            content += "\n"

        if completion.metrics:
            content += "📊 **Metrics:**\n"
            for key, value in completion.metrics.items():
                content += f"  • {key}: {value}\n"
            content += "\n"

        content += f"⏱️ **Completed at:** {completion.completed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        return content

    def cancel_task(self, task_id: str, reason: str | None = None) -> dict[str, Any]:
        """Cancel an active task."""
        try:
            # Get task from database
            tasks = self.db.get_active_tasks()
            task = None
            for t in tasks:
                if t["id"] == task_id:
                    task = t
                    break

            if not task:
                return {"status": "error", "error": "Task not found or not active"}

            # Get agent for stream info
            agent = self.registry.get_agent(task["agent_id"])
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Update database
            self.db.update_task_progress(
                task_id=task_id,
                status="cancelled",
            )

            # Send cancellation notification
            content = f"🛑 **Task Cancelled: {task['name']}**\n\n"
            if reason:
                content += f"**Reason:** {reason}\n"

            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic=task.get("zulip_topic", f"Task: {task['name']}"),
                content=content,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "message": f"Task '{task['name']}' cancelled",
                }

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send notification"),
            }

        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return {"status": "error", "error": str(e)}

    def get_active_tasks(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get list of active tasks."""
        try:
            tasks = self.db.get_active_tasks(agent_id)

            return {
                "status": "success",
                "tasks": [
                    {
                        "id": task["id"],
                        "name": task["name"],
                        "description": task["description"],
                        "status": task["status"],
                        "progress": task.get("progress_percentage"),
                        "started_at": task.get("started_at"),
                    }
                    for task in tasks
                ],
                "count": len(tasks),
            }

        except Exception as e:
            logger.error(f"Failed to get active tasks: {e}")
            return {"status": "error", "error": str(e)}
