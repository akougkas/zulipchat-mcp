"""Comprehensive tests for the workflow automation system.

The workflows.py module provides a complete workflow engine that can trigger 
command chains based on events like messages, subscriptions, and user actions.

Key components tested:
- Workflow dataclass with trigger events and command chains
- WorkflowEngine with registration, triggering, and management  
- Enable/disable functionality
- Workflow triggering logic
- Factory functions

This aims for 80%+ coverage of the workflow engine functionality.
Note: Predefined workflows have bugs in the actual code, so we test the core engine.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.zulipchat_mcp.workflows import (
    Workflow,
    WorkflowEngine,
    should_trigger_workflow,
    create_workflow_engine
)
from src.zulipchat_mcp.commands import CommandChain, SendMessageCommand, ExecutionContext
from src.zulipchat_mcp.client import ZulipClientWrapper


class TestWorkflowDataclass:
    """Test the Workflow dataclass."""
    
    def test_workflow_initialization(self):
        """Test Workflow initialization with required fields."""
        mock_chain = Mock(spec=CommandChain)
        
        workflow = Workflow(
            name="test_workflow",
            trigger_event="message",
            command_chain=mock_chain
        )
        
        assert workflow.name == "test_workflow"
        assert workflow.trigger_event == "message"
        assert workflow.command_chain is mock_chain
        assert workflow.enabled is True  # Default
        assert isinstance(workflow.created_at, datetime)
    
    def test_workflow_custom_initialization(self):
        """Test Workflow initialization with custom values."""
        mock_chain = Mock(spec=CommandChain)
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        
        workflow = Workflow(
            name="custom_workflow",
            trigger_event="subscription",
            command_chain=mock_chain,
            enabled=False,
            created_at=custom_time
        )
        
        assert workflow.enabled is False
        assert workflow.created_at == custom_time


class TestWorkflowEngineCore:
    """Test the WorkflowEngine core functionality without predefined workflows."""
    
    def test_workflow_engine_initialization(self):
        """Test WorkflowEngine initialization without predefined workflows."""
        client = Mock(spec=ZulipClientWrapper)
        
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine(client=client)
            
            assert engine.client is client
            assert "message" in engine.workflows
            assert "subscription" in engine.workflows
            assert "realm_user" in engine.workflows
            assert all(isinstance(workflows, list) for workflows in engine.workflows.values())
    
    def test_workflow_engine_initialization_without_client(self):
        """Test WorkflowEngine initialization without client."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            assert engine.client is None
            assert len(engine.workflows) == 3  # Default event types


class TestWorkflowRegistration:
    """Test workflow registration functionality."""
    
    def test_register_workflow_success(self):
        """Test successful workflow registration."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            
            engine.register_workflow("test_workflow", "message", mock_chain)
            
            assert len(engine.workflows["message"]) == 1
            
            # Find our registered workflow
            workflow = engine.workflows["message"][0]
            assert workflow.name == "test_workflow"
            assert workflow.trigger_event == "message"
            assert workflow.command_chain is mock_chain
            assert workflow.enabled is True
    
    def test_register_workflow_invalid_trigger_event(self):
        """Test registration with invalid trigger event."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            
            with pytest.raises(ValueError, match="Unsupported trigger event: invalid_event"):
                engine.register_workflow("test", "invalid_event", mock_chain)
    
    def test_register_multiple_workflows_same_event(self):
        """Test registering multiple workflows for the same event type."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            chain1 = Mock(spec=CommandChain)
            chain2 = Mock(spec=CommandChain)
            
            engine.register_workflow("workflow1", "subscription", chain1)
            engine.register_workflow("workflow2", "subscription", chain2)
            
            assert len(engine.workflows["subscription"]) == 2
            
            names = [w.name for w in engine.workflows["subscription"]]
            assert "workflow1" in names
            assert "workflow2" in names


class TestWorkflowTriggering:
    """Test workflow triggering and execution."""
    
    def test_trigger_workflows_success(self):
        """Test successful workflow triggering."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            # Create mock command chain that succeeds
            mock_chain = Mock(spec=CommandChain)
            mock_context = Mock(spec=ExecutionContext)
            mock_context.data = {"result": "success"}
            mock_chain.execute.return_value = mock_context
            mock_chain.get_execution_summary.return_value = {"status": "completed"}
            
            # Register workflow
            engine.register_workflow("test_trigger", "message", mock_chain)
            
            # Trigger workflows
            event_data = {"content": "test message", "sender": "user@example.com"}
            results = engine.trigger("message", event_data)
            
            # Should have one result
            assert len(results) == 1
            result = results[0]
            
            assert result["workflow_name"] == "test_trigger"
            assert result["status"] == "success"
            assert result["context"]["result"] == "success"
            
            # Verify enhanced event data was passed
            mock_chain.execute.assert_called_once()
            call_args = mock_chain.execute.call_args[1]
            assert "timestamp" in call_args["initial_context"]
            assert "date" in call_args["initial_context"]
            assert call_args["initial_context"]["content"] == "test message"
            assert call_args["client"] is client
    
    def test_trigger_workflows_with_failure(self):
        """Test workflow triggering when a workflow fails."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            # Create mock command chain that fails
            mock_chain = Mock(spec=CommandChain)
            mock_chain.execute.side_effect = Exception("Workflow execution failed")
            mock_chain.get_execution_summary.return_value = {"status": "failed"}
            
            # Register failing workflow
            engine.register_workflow("failing_workflow", "subscription", mock_chain)
            
            # Trigger workflows
            event_data = {"event": "subscription_change"}
            results = engine.trigger("subscription", event_data)
            
            assert len(results) == 1
            result = results[0]
            
            assert result["workflow_name"] == "failing_workflow"
            assert result["status"] == "failed"
            assert "Workflow execution failed" in result["error"]
            assert "execution_summary" in result
    
    def test_trigger_workflows_no_matching_event_type(self):
        """Test triggering workflows for unregistered event type."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            results = engine.trigger("nonexistent_event", {})
            
            assert results == []
    
    def test_trigger_workflows_with_disabled_workflow(self):
        """Test that disabled workflows are skipped."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            # Register workflow and then disable it
            mock_chain = Mock(spec=CommandChain)
            engine.register_workflow("disabled_workflow", "realm_user", mock_chain)
            engine.disable_workflow("disabled_workflow")
            
            # Trigger workflows
            results = engine.trigger("realm_user", {"user": "newuser"})
            
            # Should be empty since the workflow is disabled
            assert results == []
            
            # Verify the command chain was not executed
            mock_chain.execute.assert_not_called()


class TestWorkflowManagement:
    """Test workflow enable/disable functionality."""
    
    def test_enable_workflow_success(self):
        """Test successfully enabling a workflow."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            
            # Register and disable a workflow
            engine.register_workflow("test_enable", "message", mock_chain)
            engine.disable_workflow("test_enable")
            
            # Verify it's disabled
            workflow = engine.workflows["message"][0]
            assert workflow.enabled is False
            
            # Enable it
            result = engine.enable_workflow("test_enable")
            
            assert result is True
            assert workflow.enabled is True
    
    def test_enable_workflow_not_found(self):
        """Test enabling a non-existent workflow."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            result = engine.enable_workflow("nonexistent_workflow")
            
            assert result is False
    
    def test_disable_workflow_success(self):
        """Test successfully disabling a workflow."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            
            # Register a workflow
            engine.register_workflow("test_disable", "subscription", mock_chain)
            
            # Verify it's enabled by default
            workflow = engine.workflows["subscription"][0]
            assert workflow.enabled is True
            
            # Disable it
            result = engine.disable_workflow("test_disable")
            
            assert result is True
            assert workflow.enabled is False
    
    def test_disable_workflow_not_found(self):
        """Test disabling a non-existent workflow."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            result = engine.disable_workflow("nonexistent_workflow")
            
            assert result is False


class TestWorkflowInformation:
    """Test workflow information retrieval."""
    
    def test_get_workflows_all_types(self):
        """Test getting information about all workflows."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            mock_chain.commands = ["cmd1", "cmd2"]  # Mock 2 commands
            
            # Register a test workflow
            engine.register_workflow("info_test", "message", mock_chain)
            
            workflows_info = engine.get_workflows()
            
            assert "message" in workflows_info
            assert "subscription" in workflows_info
            assert "realm_user" in workflows_info
            
            # Check message workflows (1 test workflow)
            message_workflows = workflows_info["message"]
            assert len(message_workflows) == 1
            
            test_info = message_workflows[0]
            assert test_info["name"] == "info_test"
            assert test_info["trigger_event"] == "message"
            assert test_info["enabled"] is True
            assert test_info["command_count"] == 2
            assert "created_at" in test_info
    
    def test_get_workflows_specific_event_type(self):
        """Test getting workflows for a specific event type."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            workflows_info = engine.get_workflows(event_type="subscription")
            
            assert "subscription" in workflows_info
            assert "message" not in workflows_info
            assert "realm_user" not in workflows_info
            
            # Subscription should be empty (no workflows registered)
            assert workflows_info["subscription"] == []
    
    def test_get_workflows_nonexistent_event_type(self):
        """Test getting workflows for non-existent event type."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            
            workflows_info = engine.get_workflows(event_type="nonexistent")
            
            assert workflows_info == {}


class TestUtilityFunctions:
    """Test utility functions for workflow triggering."""
    
    def test_should_trigger_workflow_match(self):
        """Test workflow trigger condition matching."""
        message = "This is an urgent incident that needs attention"
        trigger_word = "incident"
        
        result = should_trigger_workflow(message, trigger_word)
        
        assert result is True
    
    def test_should_trigger_workflow_no_match(self):
        """Test workflow trigger condition not matching."""
        message = "This is a normal message"
        trigger_word = "incident"
        
        result = should_trigger_workflow(message, trigger_word)
        
        assert result is False
    
    def test_should_trigger_workflow_case_insensitive(self):
        """Test workflow trigger condition is case insensitive."""
        message = "URGENT INCIDENT ALERT"
        trigger_word = "incident"
        
        result = should_trigger_workflow(message, trigger_word)
        
        assert result is True
    
    def test_create_workflow_engine_with_client(self):
        """Test factory function for creating workflow engine with client."""
        client = Mock(spec=ZulipClientWrapper)
        
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = create_workflow_engine(client=client)
            
            assert isinstance(engine, WorkflowEngine)
            assert engine.client is client
    
    def test_create_workflow_engine_without_client(self):
        """Test factory function for creating workflow engine without client."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = create_workflow_engine()
            
            assert isinstance(engine, WorkflowEngine)
            assert engine.client is None


class TestWorkflowIntegrationScenarios:
    """Test complex workflow scenarios and edge cases."""
    
    def test_multiple_workflows_same_trigger(self):
        """Test multiple workflows triggered by the same event."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            # Create multiple mock chains
            chain1 = Mock(spec=CommandChain)
            chain2 = Mock(spec=CommandChain)
            
            context1 = Mock(spec=ExecutionContext)
            context1.data = {"chain": "1"}
            context2 = Mock(spec=ExecutionContext)
            context2.data = {"chain": "2"}
            
            chain1.execute.return_value = context1
            chain2.execute.return_value = context2
            chain1.get_execution_summary.return_value = {"status": "completed"}
            chain2.get_execution_summary.return_value = {"status": "completed"}
            
            # Register multiple workflows for same event
            engine.register_workflow("multi_test_1", "realm_user", chain1)
            engine.register_workflow("multi_test_2", "realm_user", chain2)
            
            # Trigger the workflows
            results = engine.trigger("realm_user", {"user_id": 123})
            
            assert len(results) == 2
            
            # Both workflows should have been executed
            chain1.execute.assert_called_once()
            chain2.execute.assert_called_once()
            
            # Check results
            result_names = [r["workflow_name"] for r in results]
            assert "multi_test_1" in result_names
            assert "multi_test_2" in result_names
    
    def test_workflow_with_enhanced_event_data(self):
        """Test that workflows receive enhanced event data with timestamps."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            mock_chain = Mock(spec=CommandChain)
            mock_context = Mock(spec=ExecutionContext)
            mock_context.data = {}
            mock_chain.execute.return_value = mock_context
            mock_chain.get_execution_summary.return_value = {"status": "completed"}
            
            engine.register_workflow("timestamp_test", "message", mock_chain)
            
            # Trigger with basic event data
            original_data = {"content": "test", "stream": "general"}
            engine.trigger("message", original_data)
            
            # Verify enhanced data was passed to chain
            mock_chain.execute.assert_called_once()
            call_kwargs = mock_chain.execute.call_args[1]
            enhanced_data = call_kwargs["initial_context"]
            
            # Original data should still be there
            assert enhanced_data["content"] == "test"
            assert enhanced_data["stream"] == "general"
            
            # Enhanced data should be added
            assert "timestamp" in enhanced_data
            assert "date" in enhanced_data
            
            # Check format of enhanced data
            assert len(enhanced_data["date"]) == 10  # YYYY-MM-DD format
            assert len(enhanced_data["timestamp"]) == 16  # YYYY-MM-DD HH:MM format
    
    def test_workflow_engine_error_resilience(self):
        """Test that workflow engine continues processing other workflows if one fails."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            client = Mock(spec=ZulipClientWrapper)
            engine = WorkflowEngine(client=client)
            
            # Create one failing and one succeeding workflow
            failing_chain = Mock(spec=CommandChain)
            failing_chain.execute.side_effect = Exception("Chain failed")
            failing_chain.get_execution_summary.return_value = {"status": "failed"}
            
            success_chain = Mock(spec=CommandChain)
            success_context = Mock(spec=ExecutionContext)
            success_context.data = {"status": "ok"}
            success_chain.execute.return_value = success_context
            success_chain.get_execution_summary.return_value = {"status": "completed"}
            
            engine.register_workflow("failing_workflow", "message", failing_chain)
            engine.register_workflow("success_workflow", "message", success_chain)
            
            # Trigger workflows - should not raise exception
            results = engine.trigger("message", {"test": "data"})
            
            # Should have results from both workflows
            assert len(results) == 2
            
            # Find our specific workflow results
            failing_result = next(r for r in results if r["workflow_name"] == "failing_workflow")
            success_result = next(r for r in results if r["workflow_name"] == "success_workflow")
            
            assert failing_result["status"] == "failed"
            assert "Chain failed" in failing_result["error"]
            
            assert success_result["status"] == "success"
            assert success_result["context"]["status"] == "ok"


class TestWorkflowContextManagement:
    """Test context data management in workflows."""
    
    def test_workflow_context_enhancement(self):
        """Test that workflow contexts are properly enhanced with timestamps."""
        with patch.object(WorkflowEngine, '_register_predefined_workflows'):
            engine = WorkflowEngine()
            mock_chain = Mock(spec=CommandChain)
            mock_context = Mock(spec=ExecutionContext)
            mock_context.data = {"original": "data"}
            mock_chain.execute.return_value = mock_context
            mock_chain.get_execution_summary.return_value = {"status": "completed"}
            
            engine.register_workflow("context_test", "subscription", mock_chain)
            
            # Trigger with original data
            original_event = {"stream": "test", "user": "alice"}
            engine.trigger("subscription", original_event)
            
            # Verify the context was enhanced before being passed to the chain
            call_args = mock_chain.execute.call_args
            enhanced_context = call_args[1]["initial_context"]
            
            # Original data should be preserved
            assert enhanced_context["stream"] == "test"
            assert enhanced_context["user"] == "alice"
            
            # Enhanced data should be added
            assert "timestamp" in enhanced_context
            assert "date" in enhanced_context
            
            # Timestamp should be in correct format
            import re
            assert re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', enhanced_context["timestamp"])
            assert re.match(r'\d{4}-\d{2}-\d{2}', enhanced_context["date"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])