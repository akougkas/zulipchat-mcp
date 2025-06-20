"""Zulip API client wrapper for MCP integration."""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from zulip import Client
from pydantic import BaseModel

from .config import ConfigManager


class ZulipMessage(BaseModel):
    """Zulip message model."""
    id: int
    sender_full_name: str
    sender_email: str
    timestamp: int
    content: str
    stream_name: Optional[str] = None
    subject: Optional[str] = None
    type: str
    reactions: List[Dict[str, Any]] = []


class ZulipStream(BaseModel):
    """Zulip stream model."""
    stream_id: int
    name: str
    description: str
    is_private: bool
    subscribers: List[str] = []


class ZulipUser(BaseModel):
    """Zulip user model."""
    user_id: int
    full_name: str
    email: str
    is_active: bool
    is_bot: bool
    avatar_url: Optional[str] = None


class ZulipClientWrapper:
    """Wrapper around Zulip client with enhanced functionality."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize Zulip client wrapper."""
        self.config_manager = config_manager or ConfigManager()
        
        if not self.config_manager.validate_config():
            raise ValueError("Invalid Zulip configuration")
        
        client_config = self.config_manager.get_zulip_client_config()
        self.client = Client(**client_config)
    
    def send_message(
        self, 
        message_type: str, 
        to: Union[str, List[str]], 
        content: str,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to a stream or user."""
        request = {
            "type": message_type,
            "content": content
        }
        
        if message_type == "stream":
            request["to"] = to if isinstance(to, str) else to[0]
            if topic:
                request["topic"] = topic
        else:  # private message
            request["to"] = to if isinstance(to, list) else [to]
        
        return self.client.send_message(request)
    
    def get_messages(
        self,
        anchor: str = "newest",
        num_before: int = 100,
        num_after: int = 0,
        narrow: Optional[List[Dict[str, str]]] = None
    ) -> List[ZulipMessage]:
        """Get messages with optional filtering."""
        request = {
            "anchor": anchor,
            "num_before": num_before,
            "num_after": num_after,
            "narrow": narrow or []
        }
        
        response = self.client.get_messages(request)
        if response["result"] == "success":
            return [
                ZulipMessage(
                    id=msg["id"],
                    sender_full_name=msg["sender_full_name"],
                    sender_email=msg["sender_email"],
                    timestamp=msg["timestamp"],
                    content=msg["content"],
                    stream_name=msg.get("display_recipient"),
                    subject=msg.get("subject"),
                    type=msg["type"],
                    reactions=msg.get("reactions", [])
                )
                for msg in response["messages"]
            ]
        return []
    
    def get_messages_from_stream(
        self, 
        stream_name: str, 
        topic: Optional[str] = None,
        hours_back: int = 24
    ) -> List[ZulipMessage]:
        """Get messages from a specific stream."""
        narrow = [{"operator": "stream", "operand": stream_name}]
        if topic:
            narrow.append({"operator": "topic", "operand": topic})
        
        # Add time filter for recent messages
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        narrow.append({
            "operator": "date", 
            "operand": cutoff_time.strftime("%Y-%m-%d")
        })
        
        return self.get_messages(narrow=narrow)
    
    def search_messages(self, query: str, num_results: int = 50) -> List[ZulipMessage]:
        """Search messages by content."""
        narrow = [{"operator": "search", "operand": query}]
        return self.get_messages(narrow=narrow, num_before=num_results)
    
    def get_streams(self, include_subscribed: bool = True) -> List[ZulipStream]:
        """Get list of streams."""
        response = self.client.get_streams(include_subscribed=include_subscribed)
        if response["result"] == "success":
            return [
                ZulipStream(
                    stream_id=stream["stream_id"],
                    name=stream["name"],
                    description=stream["description"],
                    is_private=stream.get("invite_only", False)
                )
                for stream in response["streams"]
            ]
        return []
    
    def get_users(self) -> List[ZulipUser]:
        """Get list of users."""
        response = self.client.get_users()
        if response["result"] == "success":
            return [
                ZulipUser(
                    user_id=user["user_id"],
                    full_name=user["full_name"],
                    email=user["email"],
                    is_active=user["is_active"],
                    is_bot=user["is_bot"],
                    avatar_url=user.get("avatar_url")
                )
                for user in response["members"]
            ]
        return []
    
    def add_reaction(self, message_id: int, emoji_name: str) -> Dict[str, Any]:
        """Add reaction to a message."""
        return self.client.add_reaction({
            "message_id": message_id,
            "emoji_name": emoji_name
        })
    
    def edit_message(
        self, 
        message_id: int, 
        content: Optional[str] = None,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Edit a message."""
        request = {"message_id": message_id}
        if content:
            request["content"] = content
        if topic:
            request["topic"] = topic
        
        return self.client.update_message(request)
    
    def get_daily_summary(
        self, 
        streams: Optional[List[str]] = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """Get daily message summary."""
        if not streams:
            # Get all subscribed streams
            all_streams = self.get_streams()
            streams = [s.name for s in all_streams if not s.is_private]
        
        summary = {
            "total_messages": 0,
            "streams": {},
            "top_senders": {},
            "time_range": f"Last {hours_back} hours"
        }
        
        for stream_name in streams:
            messages = self.get_messages_from_stream(stream_name, hours_back=hours_back)
            summary["streams"][stream_name] = {
                "message_count": len(messages),
                "topics": {}
            }
            
            for msg in messages:
                summary["total_messages"] += 1
                
                # Count by sender
                sender = msg.sender_full_name
                summary["top_senders"][sender] = summary["top_senders"].get(sender, 0) + 1
                
                # Count by topic
                if msg.subject:
                    topic_count = summary["streams"][stream_name]["topics"].get(msg.subject, 0)
                    summary["streams"][stream_name]["topics"][msg.subject] = topic_count + 1
        
        # Sort top senders
        summary["top_senders"] = dict(
            sorted(summary["top_senders"].items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        return summary