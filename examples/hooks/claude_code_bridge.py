#!/usr/bin/env uv run python
"""
Claude Code Hook Bridge for ZulipChat MCP
Bridges Claude Code hooks to ZulipChat MCP server for agent communication.

This script is called by Claude Code hooks and translates hook events
into MCP tool calls to send notifications to Zulip.

Run with:
  uv run examples/hooks/claude_code_bridge.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


class ClaudeCodeZulipBridge:
    """Bridge between Claude Code hooks and ZulipChat MCP."""

    def __init__(self):
        """Initialize the bridge with MCP server configuration."""
        self.mcp_server_url = os.getenv("ZULIPCHAT_MCP_URL", "http://localhost:8000")
        self.agent_id = os.getenv("CLAUDE_CODE_AGENT_ID")

        # Auto-register if no agent ID exists
        if not self.agent_id:
            self.agent_id = self._register_agent()

    def _register_agent(self) -> str | None:
        """Register Claude Code as an agent with ZulipChat MCP."""
        try:
            # Get session info from environment or generate
            session_id = os.getenv("CLAUDE_SESSION_ID", "unknown")
            project_dir = os.getenv("CLAUDE_PROJECT_DIR", os.getcwd())

            # Call MCP server to register agent
            request_data = {
                "tool": "register_agent",
                "arguments": {
                    "agent_name": f"Claude Code ({os.path.basename(project_dir)})",
                    "agent_type": "claude_code",
                    "private_stream": True,
                    "metadata": {
                        "session_id": session_id,
                        "project_dir": project_dir,
                        "host": os.uname().nodename
                    }
                }
            }

            response = self._call_mcp_tool(request_data)
            if response and response.get("status") == "success":
                agent_data = response.get("agent", {})
                agent_id = agent_data.get("id")

                # Save agent ID for future use
                if agent_id:
                    settings_path = os.path.expanduser("~/.claude/zulipchat_agent.json")
                    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
                    with open(settings_path, "w") as f:
                        json.dump({"agent_id": agent_id}, f)

                    print(f"✅ Registered with ZulipChat as agent {agent_id}", file=sys.stderr)
                    return agent_id

        except Exception as e:
            print(f"Failed to register agent: {e}", file=sys.stderr)

        return None

    def _call_mcp_tool(self, request_data: dict[str, Any]) -> dict[str, Any] | None:
        """Call an MCP tool via HTTP request."""
        try:
            req = urllib.request.Request(
                f"{self.mcp_server_url}/tool",
                data=json.dumps(request_data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.URLError as e:
            print(f"Failed to call MCP tool: {e}", file=sys.stderr)
            return None

    def handle_pre_tool_use(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle PreToolUse hook events."""
        tool_name = hook_data.get("tool_name", "Unknown")
        tool_input = hook_data.get("tool_input", {})

        # Send status update for significant tools
        if tool_name in ["Task", "Bash", "Write", "Edit"]:
            self._send_status_update(
                status="working",
                current_task=f"Executing {tool_name} tool",
                metadata={"tool_name": tool_name, "tool_input": tool_input}
            )

        # Check for sensitive operations
        if tool_name in ["Write", "Edit", "MultiEdit"]:
            file_path = tool_input.get("file_path", "")
            if any(sensitive in file_path for sensitive in [".env", "credentials", "secrets"]):
                # Request user confirmation via Zulip
                request_id = self._request_user_input(
                    question=f"Claude Code wants to modify a sensitive file: {file_path}. Allow this operation?",
                    context={"tool_name": tool_name, "file_path": file_path},
                    options=["Allow", "Deny"]
                )

                # Wait for response (simplified - in production, use async)
                response = self._wait_for_response(request_id)

                if response == "Deny":
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "User denied modification of sensitive file via Zulip"
                        }
                    }

        return {}  # Allow by default

    def handle_post_tool_use(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle PostToolUse hook events."""
        tool_name = hook_data.get("tool_name", "Unknown")
        tool_response = hook_data.get("tool_response", {})

        # Track important completions
        if tool_name == "Task":
            # Task tool completed - send completion notification
            self._send_agent_message(
                message_type="completion",
                content="Completed subagent task",
                metadata={"tool_response": tool_response}
            )

        return {}

    def handle_notification(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle Notification hook events."""
        message = hook_data.get("message", "")

        # Forward notification to Zulip
        self._send_agent_message(
            message_type="status",
            content=f"📢 {message}",
            metadata={"notification_type": "claude_code"}
        )

        return {}

    def handle_user_prompt_submit(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle UserPromptSubmit hook events."""
        prompt = hook_data.get("prompt", "")

        # Log the prompt submission
        self._send_agent_message(
            message_type="status",
            content=f"Received prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}",
            metadata={"prompt_length": len(prompt)}
        )

        return {}

    def handle_stop(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle Stop hook events."""
        # Send completion status
        self._send_status_update(
            status="idle",
            current_task="Completed response",
            metadata={"event": "stop"}
        )

        return {}

    def handle_session_start(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionStart hook events."""
        source = hook_data.get("source", "unknown")

        # Announce session start
        self._send_agent_message(
            message_type="status",
            content=f"🚀 Claude Code session started ({source})",
            metadata={
                "session_id": hook_data.get("session_id"),
                "source": source,
                "project_dir": os.getenv("CLAUDE_PROJECT_DIR", "unknown")
            }
        )

        # Return context about Zulip integration
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"ZulipChat MCP integration active. Agent ID: {self.agent_id}"
            }
        }

    def handle_session_end(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionEnd hook events."""
        reason = hook_data.get("reason", "unknown")

        # Send farewell message
        self._send_agent_message(
            message_type="status",
            content=f"👋 Claude Code session ending ({reason})",
            metadata={"reason": reason}
        )

        return {}

    def _send_agent_message(self, message_type: str, content: str, metadata: dict | None = None):
        """Send a message via the agent_message MCP tool."""
        if not self.agent_id:
            return

        request_data = {
            "tool": "agent_message",
            "arguments": {
                "agent_id": self.agent_id,
                "message_type": message_type,
                "content": content,
                "metadata": metadata or {}
            }
        }

        self._call_mcp_tool(request_data)

    def _send_status_update(self, status: str, current_task: str, metadata: dict | None = None):
        """Send a status update via the send_agent_status MCP tool."""
        if not self.agent_id:
            return

        request_data = {
            "tool": "send_agent_status",
            "arguments": {
                "agent_id": self.agent_id,
                "status": status,
                "current_task": current_task,
                "progress_percentage": metadata.get("progress") if metadata else None,
                "estimated_time": metadata.get("eta") if metadata else None
            }
        }

        self._call_mcp_tool(request_data)

    def _request_user_input(self, question: str, context: dict, options: list | None = None) -> str | None:
        """Request user input via Zulip."""
        if not self.agent_id:
            return None

        request_data = {
            "tool": "request_user_input",
            "arguments": {
                "agent_id": self.agent_id,
                "question": question,
                "context": context,
                "options": options,
                "timeout_seconds": 300
            }
        }

        response = self._call_mcp_tool(request_data)
        if response and response.get("status") == "success":
            return response.get("request_id")

        return None

    def _wait_for_response(self, request_id: str, timeout: int = 60) -> str | None:
        """Wait for user response (simplified version)."""
        if not self.agent_id or not request_id:
            return None

        # In production, this would poll or use webhooks
        # For now, we'll just return None (timeout)
        import time
        time.sleep(2)  # Brief wait to simulate checking

        request_data = {
            "tool": "wait_for_response",
            "arguments": {
                "agent_id": self.agent_id,
                "request_id": request_id,
                "timeout": timeout
            }
        }

        response = self._call_mcp_tool(request_data)
        if response and response.get("status") == "success":
            return response.get("response")

        return None

    def process_hook(self, hook_data: dict[str, Any]) -> dict[str, Any]:
        """Process a Claude Code hook event."""
        event_name = hook_data.get("hook_event_name", "")

        handlers = {
            "PreToolUse": self.handle_pre_tool_use,
            "PostToolUse": self.handle_post_tool_use,
            "Notification": self.handle_notification,
            "UserPromptSubmit": self.handle_user_prompt_submit,
            "Stop": self.handle_stop,
            "SessionStart": self.handle_session_start,
            "SessionEnd": self.handle_session_end
        }

        handler = handlers.get(event_name)
        if handler:
            try:
                return handler(hook_data)
            except Exception as e:
                print(f"Error handling {event_name}: {e}", file=sys.stderr)

        return {}


def main():
    """Main entry point for the hook bridge."""
    try:
        # Read hook data from stdin
        hook_data = json.load(sys.stdin)

        # Initialize bridge
        bridge = ClaudeCodeZulipBridge()

        # Process the hook
        result = bridge.process_hook(hook_data)

        # Output result if any
        if result:
            print(json.dumps(result))

        sys.exit(0)

    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Hook processing failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
