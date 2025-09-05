"""Workflow automation system for ZulipChat MCP.

This module provides a workflow engine that can trigger command chains based on 
events like messages, subscriptions, and user actions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .client import ZulipClientWrapper
from .commands import CommandChain, ProcessDataCommand, SendMessageCommand

logger = logging.getLogger(__name__)


@dataclass
class Workflow:
    """Represents an automated workflow triggered by events."""

    name: str
    trigger_event: str
    command_chain: CommandChain
    enabled: bool = True
    created_at: datetime = datetime.now()


class WorkflowEngine:
    """Engine for managing and executing automated workflows."""

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

        # Register predefined workflows
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

                # Execute the workflow's command chain
                context = workflow.command_chain.execute(
                    initial_context=event_data,
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
        """Register predefined workflows."""

        # ONBOARDING_WORKFLOW: Welcome new users
        onboarding_chain = CommandChain("onboarding_workflow")

        # Set welcome message parameters
        onboarding_chain.add_command(ProcessDataCommand(
            name="set_welcome_params",
            processor=lambda event_data: {
                "message_type": "private",
                "to": event_data.get("user_id", event_data.get("email", "unknown")),
                "content": f"Welcome to Zulip, {event_data.get('full_name', 'new user')}! "
                          f"Feel free to explore the streams and join conversations. "
                          f"If you have any questions, don't hesitate to ask!"
            },
            input_key="dummy",
            output_key="welcome_params"
        ))

        # Extract message parameters
        onboarding_chain.add_command(ProcessDataCommand(
            name="extract_welcome_type",
            processor=lambda params: params["message_type"],
            input_key="welcome_params",
            output_key="message_type"
        ))

        onboarding_chain.add_command(ProcessDataCommand(
            name="extract_welcome_to",
            processor=lambda params: params["to"],
            input_key="welcome_params",
            output_key="to"
        ))

        onboarding_chain.add_command(ProcessDataCommand(
            name="extract_welcome_content",
            processor=lambda params: params["content"],
            input_key="welcome_params",
            output_key="content"
        ))

        # Send welcome message
        onboarding_chain.add_command(SendMessageCommand(name="send_welcome"))

        self.register_workflow("ONBOARDING_WORKFLOW", "realm_user", onboarding_chain)

        # INCIDENT_WORKFLOW: Create incident stream when #incident is mentioned
        incident_chain = CommandChain("incident_workflow")

        # Process incident message and create stream notification
        incident_chain.add_command(ProcessDataCommand(
            name="set_incident_params",
            processor=lambda event_data: {
                "message_type": "stream",
                "to": "incidents",
                "topic": f"Incident - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": f"🚨 **INCIDENT DETECTED** 🚨\n\n"
                          f"Original message from {event_data.get('sender_full_name', 'unknown')}:\n"
                          f"> {event_data.get('content', 'No content')}\n\n"
                          f"Stream: #{event_data.get('stream_name', 'unknown')}\n"
                          f"Topic: {event_data.get('subject', 'unknown')}\n\n"
                          f"Please investigate and respond appropriately."
            },
            input_key="dummy",
            output_key="incident_params"
        ))

        # Extract incident parameters
        incident_chain.add_command(ProcessDataCommand(
            name="extract_incident_type",
            processor=lambda params: params["message_type"],
            input_key="incident_params",
            output_key="message_type"
        ))

        incident_chain.add_command(ProcessDataCommand(
            name="extract_incident_to",
            processor=lambda params: params["to"],
            input_key="incident_params",
            output_key="to"
        ))

        incident_chain.add_command(ProcessDataCommand(
            name="extract_incident_topic",
            processor=lambda params: params["topic"],
            input_key="incident_params",
            output_key="topic"
        ))

        incident_chain.add_command(ProcessDataCommand(
            name="extract_incident_content",
            processor=lambda params: params["content"],
            input_key="incident_params",
            output_key="content"
        ))

        # Send incident notification
        incident_chain.add_command(SendMessageCommand(name="send_incident_notification"))

        self.register_workflow("INCIDENT_WORKFLOW", "message", incident_chain)

        # CODE_REVIEW_WORKFLOW: Notify reviewers when PR: is mentioned
        review_chain = CommandChain("code_review_workflow")

        # Process PR message and notify reviewers
        review_chain.add_command(ProcessDataCommand(
            name="set_review_params",
            processor=lambda event_data: {
                "message_type": "stream",
                "to": "code-review",
                "topic": "Pull Request Reviews",
                "content": f"📋 **Code Review Request** 📋\n\n"
                          f"From: {event_data.get('sender_full_name', 'unknown')}\n"
                          f"Message: {event_data.get('content', 'No content')}\n\n"
                          f"Original stream: #{event_data.get('stream_name', 'unknown')}\n"
                          f"Topic: {event_data.get('subject', 'unknown')}\n\n"
                          f"@**code-reviewers** please review when available."
            },
            input_key="dummy",
            output_key="review_params"
        ))

        # Extract review parameters
        review_chain.add_command(ProcessDataCommand(
            name="extract_review_type",
            processor=lambda params: params["message_type"],
            input_key="review_params",
            output_key="message_type"
        ))

        review_chain.add_command(ProcessDataCommand(
            name="extract_review_to",
            processor=lambda params: params["to"],
            input_key="review_params",
            output_key="to"
        ))

        review_chain.add_command(ProcessDataCommand(
            name="extract_review_topic",
            processor=lambda params: params["topic"],
            input_key="review_params",
            output_key="topic"
        ))

        review_chain.add_command(ProcessDataCommand(
            name="extract_review_content",
            processor=lambda params: params["content"],
            input_key="review_params",
            output_key="content"
        ))

        # Send review notification
        review_chain.add_command(SendMessageCommand(name="send_review_notification"))

        self.register_workflow("CODE_REVIEW_WORKFLOW", "message", review_chain)

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


# Helper functions for triggering workflows based on message content
def should_trigger_incident_workflow(message_content: str) -> bool:
    """Check if message should trigger incident workflow."""
    return "#incident" in message_content.lower()


def should_trigger_code_review_workflow(message_content: str) -> bool:
    """Check if message should trigger code review workflow."""
    return "PR:" in message_content or "pr:" in message_content.lower()


# Factory function for creating workflow engine with default client
def create_workflow_engine(client: ZulipClientWrapper | None = None) -> WorkflowEngine:
    """Create a workflow engine instance.
    
    Args:
        client: Optional Zulip client wrapper
        
    Returns:
        Configured workflow engine
    """
    return WorkflowEngine(client=client)
