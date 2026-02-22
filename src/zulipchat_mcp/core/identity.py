"""Identity management for multi-credential support in Zulip MCP.

This module provides identity management with support for user and bot
credentials with clear capability boundaries. Admin identity is not used.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..config import ConfigManager
from ..utils.logging import get_logger
from .client import ZulipClientWrapper
from .exceptions import AuthenticationError

logger = get_logger(__name__)


class IdentityType(Enum):
    """Types of identities supported by the system."""

    USER = "user"
    BOT = "bot"
    ADMIN = "admin"  # Deprecated: not used or created


@dataclass
class Capability:
    """Represents a capability that an identity can have."""

    name: str
    description: str
    requires_admin: bool = False
    requires_bot: bool = False


@dataclass
class Identity:
    """Base identity class with credentials and capabilities."""

    type: IdentityType
    email: str
    api_key: str
    site: str = ""  # Default empty, will be set from config if not provided
    name: str = ""  # Use 'name' for compatibility with tests
    display_name: str = field(default="", init=False)  # Computed from name
    capabilities: set[str] = field(default_factory=set)
    _client: ZulipClientWrapper | None = field(default=None, init=False, repr=False)
    _config_manager: ConfigManager | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize capabilities based on identity type."""
        # Set display_name from name for backward compatibility
        self.display_name = self.name or self.email.split("@")[0]

        if self.type == IdentityType.USER:
            self.capabilities = {
                "send_message",
                "read_messages",
                "edit_own_messages",
                "search",
                "upload_files",
                "subscribe_streams",
                "get_presence",
                "add_reactions",
            }
        elif self.type == IdentityType.BOT:
            self.capabilities = {
                "send_message",
                "read_messages",
                "react_messages",
                "stream_events",
                "scheduled_messages",
                "bulk_read",
                "webhook_integration",
                "automated_responses",
            }
        elif self.type == IdentityType.ADMIN:
            # Admin identity is deprecated and should not be instantiated
            self.capabilities = set()

    @property
    def client(self) -> ZulipClientWrapper:
        """Get or create ZulipClientWrapper for this identity."""
        if self._client is None:
            # Create a minimal config manager for this identity if not available
            if self._config_manager is None:
                from ..config import ZulipConfig

                temp_config = ZulipConfig(
                    email=self.email, api_key=self.api_key, site=self.site
                )
                # Create a temporary ConfigManager with this identity's config
                temp_config_manager = ConfigManager()
                temp_config_manager.config = temp_config
                self._config_manager = temp_config_manager

            # Determine if this should use bot identity based on the identity type
            use_bot_identity = self.type == IdentityType.BOT

            self._client = ZulipClientWrapper(
                config_manager=self._config_manager, use_bot_identity=use_bot_identity
            )
        return self._client

    def has_capability(self, capability: str) -> bool:
        """Check if this identity has a specific capability."""
        return "all" in self.capabilities or capability in self.capabilities

    def close(self) -> None:
        """Close the client connection."""
        self._client = None

    def __str__(self) -> str:
        """String representation of identity."""
        return f"Identity(type={self.type.name}, email={self.email}, name={self.name})"

    def __eq__(self, other: object) -> bool:
        """Equality comparison based on type, email, and name."""
        if not isinstance(other, Identity):
            return False
        return (
            self.type == other.type
            and self.email == other.email
            and self.name == other.name
        )


class IdentityManager:
    """Manages multiple identities with capability-based access control."""

    # Capability requirements for tool categories (lightweight; let API enforce perms)
    TOOL_CAPABILITIES = {
        # Core Messaging
        "messaging.message": ["send_message"],
        "messaging.search_messages": ["read_messages"],
        "messaging.edit_message": ["edit_own_messages"],
        "messaging.bulk_operations": ["bulk_read"],
        # Stream Management (no pre-gating; Zulip will enforce)
        "streams.manage_streams": [],
        "streams.manage_topics": [],
        "streams.get_stream_info": ["read_messages"],
        # Event Streaming
        "events.register_events": ["stream_events"],
        "events.get_events": ["stream_events"],
        "events.listen_events": ["stream_events"],
        # User & Authentication (no pre-gating for general operations)
        "users.manage_users": [],
        "users.switch_identity": [],  # Always allowed
        "users.manage_user_groups": [],
        # Search & Analytics
        "search.advanced_search": ["search"],
        "search.analytics": ["read_messages"],
        # File Management
        "files.upload_file": ["upload_files"],
        "files.manage_files": ["upload_files"],
    }

    def __init__(self, config: ConfigManager) -> None:
        """Initialize identity manager with configuration.

        Args:
            config: Configuration manager with credentials
        """
        self.config = config
        self.identities: dict[IdentityType, Identity] = {}
        self.current_identity: IdentityType | None = None
        self._temporary_identity: IdentityType | None = None
        # Removed: _identity_stack - over-engineering with nested contexts

        # Initialize identities
        self._initialize_identities()

    def _initialize_identities(self) -> None:
        """Initialize available identities from configuration."""
        config_data = self.config.config
        email: str | None = getattr(self.config, "email", config_data.email)
        api_key: str | None = getattr(self.config, "api_key", config_data.api_key)
        site: str | None = getattr(self.config, "site", config_data.site)

        if not email or not api_key or not site:
            raise ValueError("User credentials (email, api_key, site) are required")

        has_bot_credentials = self.config.has_bot_credentials()
        bot_email = (
            getattr(self.config, "bot_email", config_data.bot_email)
            if has_bot_credentials
            else None
        )
        bot_api_key = (
            getattr(self.config, "bot_api_key", config_data.bot_api_key)
            if has_bot_credentials
            else None
        )
        bot_name = getattr(self.config, "bot_name", config_data.bot_name) or "Bot"

        # User identity (always available)
        user_identity = Identity(
            type=IdentityType.USER,
            email=email,
            api_key=api_key,
            site=site,
            name=email.split("@")[0],
        )
        # Provide the config manager to user identity
        user_identity._config_manager = self.config
        self.identities[IdentityType.USER] = user_identity
        self.current_identity = IdentityType.USER

        # Bot identity (optional) - only add if configured
        if has_bot_credentials and bot_email and bot_api_key:
            bot_identity = Identity(
                type=IdentityType.BOT,
                email=bot_email,
                api_key=bot_api_key,
                site=site,
                name=bot_name,
            )
            # Provide the config manager to bot identity
            bot_identity._config_manager = self.config
            self.identities[IdentityType.BOT] = bot_identity

        # Admin identity is deprecated; do not create/admin-detect

    def _check_admin_privileges(self) -> None:  # Deprecated
        return None

    def get_current_identity(self) -> Identity:
        """Get the current active identity.

        Returns:
            Current active identity

        Raises:
            AuthenticationError: If no identity is available
        """
        identity_type = self._temporary_identity or self.current_identity
        if not identity_type:
            raise AuthenticationError("No identity configured")

        identity = self.identities.get(identity_type)
        if not identity:
            raise AuthenticationError(f"Identity {identity_type.value} not available")

        return identity

    def switch_identity(
        self, identity_type: IdentityType, persist: bool = False, validate: bool = True
    ) -> dict[str, Any]:
        """Switch to a different identity.

        Args:
            identity_type: Type of identity to switch to
            persist: If True, make this the default identity
            validate: If True, validate the identity credentials

        Returns:
            Status response with identity information

        Raises:
            AuthenticationError: If identity is not available or invalid
        """
        identity = self.identities.get(identity_type)
        if not identity:
            raise AuthenticationError(f"Identity {identity_type.value} not configured")

        if validate:
            # Validate by making a simple API call (no args)
            try:
                result = identity.client.get_users()
                if result.get("result") != "success":
                    raise AuthenticationError(
                        f"Failed to validate {identity_type.value} credentials"
                    )
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to validate {identity_type.value} credentials: {e}"
                ) from e

        if persist:
            self.current_identity = identity_type
            self._temporary_identity = None
        else:
            self._temporary_identity = identity_type

        return {
            "status": "success",
            "identity": identity_type.value,
            "email": identity.email,
            "display_name": identity.display_name,
            "name": identity.name,
            "capabilities": list(identity.capabilities),
            "persistent": persist,
        }

    @asynccontextmanager
    async def use_identity(
        self, identity_type: IdentityType
    ) -> AsyncIterator[Identity]:
        """Context manager for temporarily using a different identity.

        Args:
            identity_type: Type of identity to use

        Yields:
            The requested identity

        Raises:
            AuthenticationError: If identity is not available
        """
        identity = self.identities.get(identity_type)
        if not identity:
            raise AuthenticationError(f"Identity {identity_type.value} not configured")

        # Simple context switching - no stack management
        previous_identity = self._temporary_identity
        self._temporary_identity = identity_type
        try:
            yield identity
        finally:
            # Restore previous identity (simple restore)
            self._temporary_identity = previous_identity

    def check_capability(
        self, tool: str, identity_type: IdentityType | None = None
    ) -> bool:
        """Check if an identity has the capability to use a tool.

        Args:
            tool: Tool name (e.g., "messaging.message")
            identity_type: Identity to check (uses current if None)

        Returns:
            True if the identity has the required capability
        """
        if identity_type:
            identity = self.identities.get(identity_type)
        else:
            try:
                identity = self.get_current_identity()
            except AuthenticationError:
                return False

        if not identity:
            return False

        # Check if tool requires specific capabilities
        required_capabilities = self.TOOL_CAPABILITIES.get(tool, [])
        if not required_capabilities:
            return True  # No specific requirements

        # Check if identity has any of the required capabilities
        for capability in required_capabilities:
            if identity.has_capability(capability):
                return True

        return False

    def select_best_identity(
        self, tool: str, preferred: IdentityType | None = None
    ) -> Identity:
        """Select identity using a simple policy:
        - USER for read/search/edit/list/admin-less ops
        - BOT for sending messages back (agent-facing writes)
        """
        # Honor explicit preference if available
        if preferred and preferred in self.identities:
            return self.identities[preferred]

        tool_lower = tool.lower()
        # Heuristic: tools that "send" or agent tools use BOT; else USER
        use_bot = any(
            kw in tool_lower
            for kw in [
                "agent_message",
                "send_agent_status",
                "request_user_input",
                "start_task",
                "update_task_progress",
                "complete_task",
                "poll_agent_events",
            ]
        ) or (tool_lower.startswith("messaging.message") and False)

        if use_bot and IdentityType.BOT in self.identities:
            return self.identities[IdentityType.BOT]

        # Default to USER
        return self.identities[IdentityType.USER]

    async def execute_with_identity(
        self,
        tool: str,
        params: dict[str, Any],
        executor: Callable[[ZulipClientWrapper, dict[str, Any]], Awaitable[Any]],
        preferred_identity: IdentityType | None = None,
    ) -> Any:
        """Execute a tool with the appropriate identity.

        Args:
            tool: Tool name to execute
            params: Tool parameters
            executor: Async function to execute the tool
            preferred_identity: Preferred identity to use

        Returns:
            Tool execution result

        Raises:
            PermissionError: If no identity has required capabilities
        """
        identity = self.select_best_identity(tool, preferred_identity)

        # Execute with the selected identity
        async with self.use_identity(identity.type):
            logger.debug(
                f"Executing {tool} as {identity.type.value} ({identity.email})"
            )
            return await executor(identity.client, params)

    def get_available_identities(self) -> dict[str, Any]:
        """Get information about all available identities.

        Returns:
            Dictionary with identity information
        """
        available: dict[str, dict[str, Any]] = {}
        result: dict[str, Any] = {
            "current": self.current_identity.value if self.current_identity else None,
            "temporary": (
                self._temporary_identity.value if self._temporary_identity else None
            ),
            "available": available,
        }

        for identity_type, identity in self.identities.items():
            available[identity_type.value] = {
                "email": identity.email,
                "display_name": identity.display_name,
                "name": identity.name,
                "capabilities": list(identity.capabilities),
                "site": identity.site,
            }

        return result

    def close_all(self) -> None:
        """Close all client connections."""
        for identity in self.identities.values():
            identity.close()
