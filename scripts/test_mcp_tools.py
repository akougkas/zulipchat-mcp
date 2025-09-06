#!/usr/bin/env uv run python
"""
Interactive test script for ZulipChat MCP Agent Communication System (legacy)
Tests all agent-related MCP tools directly

Run with:
  uv run examples/test_mcp_tools_legacy.py
  uv run examples/test_mcp_tools_legacy.py --interactive
"""

import json
import asyncio
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, Optional
import sys
import time


class MCPTester:
    """Test harness for MCP tools."""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        """Initialize the tester."""
        self.server_url = server_url
        self.agent_id = None
        self.request_id = None
        self.task_id = None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via JSON-RPC."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        try:
            req = urllib.request.Request(
                self.server_url,
                data=json.dumps(request_data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("result", result)
                
        except Exception as e:
            return {"error": str(e)}
    
    def test_register_agent(self):
        """Test agent registration."""
        print("\n📝 Testing Agent Registration...")
        print("-" * 40)
        
        result = self.call_tool("register_agent", {
            "agent_name": f"Test Agent {datetime.now().strftime('%H:%M:%S')}",
            "agent_type": "claude_code",
            "private_stream": True
        })
        
        if "agent" in result:
            self.agent_id = result["agent"]["id"]
            print(f"✅ Agent registered successfully!")
            print(f"   Agent ID: {self.agent_id}")
            print(f"   Stream: {result['agent'].get('stream_name')}")
        else:
            print(f"❌ Registration failed: {result}")
        
        return result
    
    def test_send_message(self):
        """Test sending agent message."""
        if not self.agent_id:
            print("⚠️  No agent ID - register agent first")
            return
        
        print("\n💬 Testing Agent Message...")
        print("-" * 40)
        
        result = self.call_tool("agent_message", {
            "agent_id": self.agent_id,
            "message_type": "status",
            "content": "🧪 Test message from MCP tester",
            "metadata": {"test": True, "timestamp": datetime.now().isoformat()}
        })
        
        if result.get("status") == "success":
            print("✅ Message sent successfully!")
        else:
            print(f"❌ Message failed: {result}")
        
        return result
    
    def test_status_update(self):
        """Test sending status update."""
        if not self.agent_id:
            print("⚠️  No agent ID - register agent first")
            return
        
        print("\n📊 Testing Status Update...")
        print("-" * 40)
        
        result = self.call_tool("send_agent_status", {
            "agent_id": self.agent_id,
            "status": "working",
            "current_task": "Running integration tests",
            "progress_percentage": 75,
            "estimated_time": "2 minutes remaining"
        })
        
        if result.get("status") == "success":
            print("✅ Status update sent!")
            print("   Check Zulip for progress bar visualization")
        else:
            print(f"❌ Status update failed: {result}")
        
        return result
    
    def test_request_input(self):
        """Test requesting user input."""
        if not self.agent_id:
            print("⚠️  No agent ID - register agent first")
            return
        
        print("\n❓ Testing User Input Request...")
        print("-" * 40)
        
        result = self.call_tool("request_user_input", {
            "agent_id": self.agent_id,
            "question": "Which test should I run next?",
            "context": {"current_test": "integration", "time": datetime.now().isoformat()},
            "options": ["Task lifecycle test", "Stream management test", "Skip remaining tests"],
            "timeout_seconds": 60
        })
        
        if result.get("status") == "success":
            self.request_id = result.get("request_id")
            print("✅ Input request sent!")
            print(f"   Request ID: {self.request_id}")
            print("   Check Zulip and reply with 1, 2, or 3")
        else:
            print(f"❌ Input request failed: {result}")
        
        return result
    
    def test_start_task(self):
        """Test starting a task."""
        if not self.agent_id:
            print("⚠️  No agent ID - register agent first")
            return
        
        print("\n🚀 Testing Task Start...")
        print("-" * 40)
        
        result = self.call_tool("start_task", {
            "agent_id": self.agent_id,
            "task_name": "Integration Test Task",
            "task_description": "Testing the task lifecycle management system",
            "subtasks": [
                "Initialize test environment",
                "Run unit tests",
                "Run integration tests",
                "Generate report"
            ]
        })
        
        if result.get("status") == "success":
            self.task_id = result.get("task_id")
            print("✅ Task started!")
            print(f"   Task ID: {self.task_id}")
        else:
            print(f"❌ Task start failed: {result}")
        
        return result
    
    def test_update_task(self):
        """Test updating task progress."""
        if not self.task_id:
            print("⚠️  No task ID - start task first")
            return
        
        print("\n📈 Testing Task Progress Update...")
        print("-" * 40)
        
        result = self.call_tool("update_task_progress", {
            "task_id": self.task_id,
            "subtask_completed": "Initialize test environment",
            "progress_percentage": 25,
            "blockers": None
        })
        
        if result.get("status") == "success":
            print("✅ Task progress updated!")
        else:
            print(f"❌ Task update failed: {result}")
        
        return result
    
    def test_complete_task(self):
        """Test completing a task."""
        if not self.task_id:
            print("⚠️  No task ID - start task first")
            return
        
        print("\n✅ Testing Task Completion...")
        print("-" * 40)
        
        result = self.call_tool("complete_task", {
            "task_id": self.task_id,
            "summary": "All tests completed successfully",
            "outputs": {
                "tests_run": 4,
                "tests_passed": 4,
                "files_created": ["test_results.json"],
                "files_modified": ["test_integration.py"]
            },
            "metrics": {
                "duration": "5 minutes",
                "coverage": "85%",
                "performance": "Excellent"
            }
        })
        
        if result.get("status") == "success":
            print("✅ Task completed!")
            print("   Check Zulip for detailed completion report")
        else:
            print(f"❌ Task completion failed: {result}")
        
        return result
    
    def test_stream_management(self):
        """Test stream management tools."""
        print("\n🌊 Testing Stream Management...")
        print("-" * 40)
        
        # Create a test stream
        result = self.call_tool("create_stream", {
            "name": f"test-stream-{datetime.now().strftime('%H%M%S')}",
            "description": "Test stream for MCP integration",
            "is_private": False,
            "is_announcement_only": False
        })
        
        if result.get("status") == "success":
            print("✅ Stream created!")
            stream_id = result.get("stream_id")
            
            # Test stream organization
            org_result = self.call_tool("organize_streams_by_project", {
                "project_mapping": {
                    "TestProject": ["test-stream-*"],
                    "Agents": ["ai-agents/*"]
                }
            })
            
            if org_result.get("status") == "success":
                print("✅ Streams organized by project!")
                projects = org_result.get("projects", {})
                for project, streams in projects.items():
                    print(f"   {project}: {len(streams)} streams")
        else:
            print(f"❌ Stream creation failed: {result}")
    
    def run_all_tests(self):
        """Run all tests in sequence."""
        print("=" * 50)
        print("🧪 ZulipChat MCP Integration Test Suite")
        print("=" * 50)
        
        # Check server health first
        print("\n🏥 Checking server health...")
        try:
            req = urllib.request.Request(f"{self.server_url}/health")
            with urllib.request.urlopen(req, timeout=5) as response:
                print("✅ Server is healthy")
        except Exception as e:
            print(f"❌ Server health check failed: {e}")
            print("Make sure MCP server is running: uv run mcp")
            return
        
        # Run test sequence
        tests = [
            ("Agent Registration", self.test_register_agent),
            ("Send Message", self.test_send_message),
            ("Status Update", self.test_status_update),
            ("Start Task", self.test_start_task),
            ("Update Task", self.test_update_task),
            ("Complete Task", self.test_complete_task),
            ("Request Input", self.test_request_input),
            ("Stream Management", self.test_stream_management),
        ]
        
        for name, test_func in tests:
            try:
                test_func()
                time.sleep(1)  # Brief pause between tests
            except Exception as e:
                print(f"❌ {name} failed with error: {e}")
        
        print("\n" + "=" * 50)
        print("✨ Test suite complete!")
        print("Check your Zulip streams for all the messages!")
        print("=" * 50)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ZulipChat MCP Agent System")
    parser.add_argument("--server", default="http://localhost:8000", help="MCP server URL")
    parser.add_argument("--interactive", action="store_true", help="Run interactive mode")
    
    args = parser.parse_args()
    
    tester = MCPTester(args.server)
    
    if args.interactive:
        print("🎮 Interactive Mode")
        print("Commands: register, message, status, input, task_start, task_update, task_complete, stream, all, quit")
        
        commands = {
            "register": tester.test_register_agent,
            "message": tester.test_send_message,
            "status": tester.test_status_update,
            "input": tester.test_request_input,
            "task_start": tester.test_start_task,
            "task_update": tester.test_update_task,
            "task_complete": tester.test_complete_task,
            "stream": tester.test_stream_management,
            "all": tester.run_all_tests,
        }
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                if cmd == "quit":
                    break
                elif cmd in commands:
                    commands[cmd]()
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        tester.run_all_tests()


if __name__ == "__main__":
    main()