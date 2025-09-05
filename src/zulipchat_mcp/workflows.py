"""Workflow automation system for ZulipChat MCP.

This module provides a workflow engine that can trigger command chains based on 
events like messages, subscriptions, and user actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .client import ZulipClientWrapper
from .commands import CommandChain, SendMessageCommand

logger = logging.getLogger(__name__)


@dataclass
class Workflow:
    """Represents an automated workflow triggered by events."""

    name: str
    trigger_event: str
    command_chain: CommandChain
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class WorkflowEngine:
    """Simple engine for executing basic workflows."""

    def __init__(self, client: ZulipClientWrapper | None = None):
        """Initialize workflow engine.

        Args:
            client: Zulip client wrapper for executing workflows
        """
        self.client = client
        self.workflows: dict[str, list[Workflow]] = {
            "message": [],
            "subscription": [],
            "realm_user": []
        }

        # Register basic predefined workflows
        self._register_predefined_workflows()

    def register_workflow(
        self,
        name: str,
        trigger_event: str,
        command_chain: CommandChain
    ) -> None:
        """Register a workflow with the engine.
        
        Args:
            name: Workflow name/identifier
            trigger_event: Event type that triggers the workflow
            command_chain: Command chain to execute when triggered
            
        Raises:
            ValueError: If trigger_event is not supported
        """
        if trigger_event not in self.workflows:
            raise ValueError(f"Unsupported trigger event: {trigger_event}")

        workflow = Workflow(
            name=name,
            trigger_event=trigger_event,
            command_chain=command_chain
        )

        self.workflows[trigger_event].append(workflow)
        logger.info(f"Registered workflow '{name}' for event '{trigger_event}'")

    def trigger(self, event_type: str, event_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Trigger workflows matching the given event type.
        
        Args:
            event_type: Type of event that occurred
            event_data: Event data to pass to workflows
            
        Returns:
            List of workflow execution results
        """
        if event_type not in self.workflows:
            logger.debug(f"No workflows registered for event type: {event_type}")
            return []

        results = []
        matching_workflows = self.workflows[event_type]

        logger.info(f"Triggering {len(matching_workflows)} workflows for event: {event_type}")

        for workflow in matching_workflows:
            if not workflow.enabled:
                logger.debug(f"Skipping disabled workflow: {workflow.name}")
                continue

            try:
                logger.info(f"Executing workflow: {workflow.name}")

                # Add dynamic timestamps to context for workflow templates
                enhanced_event_data = event_data.copy()
                enhanced_event_data["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M')
                enhanced_event_data["date"] = datetime.now().strftime('%Y-%m-%d')

                # Execute the workflow's command chain
                context = workflow.command_chain.execute(
                    initial_context=enhanced_event_data,
                    client=self.client
                )

                result = {
                    "workflow_name": workflow.name,
                    "status": "success",
                    "execution_summary": workflow.command_chain.get_execution_summary(),
                    "context": context.data
                }

                results.append(result)
                logger.info(f"Workflow '{workflow.name}' completed successfully")

            except Exception as e:
                logger.error(f"Workflow '{workflow.name}' failed: {e}")
                result = {
                    "workflow_name": workflow.name,
                    "status": "failed",
                    "error": str(e),
                    "execution_summary": workflow.command_chain.get_execution_summary()
                }
                results.append(result)

        return results

    def _register_predefined_workflows(self) -> None:
        """Register basic predefined workflows."""

        # Simple incident workflow
        incident_chain = CommandChain("incident_workflow")
        incident_chain.add_command(SendMessageCommand(
            name="send_incident",
            message_type="stream",
            to="incidents",
            topic="Incident - {timestamp}",
            content="🚨 **INCIDENT DETECTED** 🚨\n\nPlease investigate and respond appropriately."
        ))
        self.register_workflow("INCIDENT_WORKFLOW", "message", incident_chain)

        # Simple standup workflow
        standup_chain = CommandChain("standup_workflow")
        standup_chain.add_command(SendMessageCommand(
            name="send_standup",
            message_type="stream",
            to="standup",
            topic="Standup - {date}",
            content="📋 **Daily Standup**\n\nWhat did you work on yesterday?\nWhat are you working on today?\nAny blockers?"
        ))
        self.register_workflow("STANDUP_WORKFLOW", "message", standup_chain)

    def get_workflows(self, event_type: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Get information about registered workflows.
        
        Args:
            event_type: Optional event type to filter by
            
        Returns:
            Dictionary of workflows grouped by event type
        """
        result = {}

        event_types = [event_type] if event_type else self.workflows.keys()

        for evt_type in event_types:
            if evt_type in self.workflows:
                result[evt_type] = [
                    {
                        "name": workflow.name,
                        "trigger_event": workflow.trigger_event,
                        "enabled": workflow.enabled,
                        "created_at": workflow.created_at.isoformat(),
                        "command_count": len(workflow.command_chain.commands)
                    }
                    for workflow in self.workflows[evt_type]
                ]

        return result

    def enable_workflow(self, workflow_name: str) -> bool:
        """Enable a workflow by name.
        
        Args:
            workflow_name: Name of workflow to enable
            
        Returns:
            True if workflow was found and enabled, False otherwise
        """
        for workflows in self.workflows.values():
            for workflow in workflows:
                if workflow.name == workflow_name:
                    workflow.enabled = True
                    logger.info(f"Enabled workflow: {workflow_name}")
                    return True

        logger.warning(f"Workflow not found: {workflow_name}")
        return False

    def disable_workflow(self, workflow_name: str) -> bool:
        """Disable a workflow by name.
        
        Args:
            workflow_name: Name of workflow to disable
            
        Returns:
            True if workflow was found and disabled, False otherwise
        """
        for workflows in self.workflows.values():
            for workflow in workflows:
                if workflow.name == workflow_name:
                    workflow.enabled = False
                    logger.info(f"Disabled workflow: {workflow_name}")
                    return True

        logger.warning(f"Workflow not found: {workflow_name}")
        return False


# Simple trigger check
def should_trigger_workflow(message_content: str, trigger_word: str) -> bool:
    """Check if message should trigger a workflow."""
    return trigger_word in message_content.lower()


# Factory function for creating workflow engine with default client
def create_workflow_engine(client: ZulipClientWrapper | None = None) -> WorkflowEngine:
    """Create a workflow engine instance.
    
    Args:
        client: Optional Zulip client wrapper
        
    Returns:
        Configured workflow engine
    """
    return WorkflowEngine(client=client)
