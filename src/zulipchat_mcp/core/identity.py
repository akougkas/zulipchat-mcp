"""Identity management for multi-credential support in Zulip MCP.

This module provides identity management with support for user, bot, and admin
credentials with clear capability boundaries.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..config import ConfigManager
from ..utils.logging import get_logger
from .client import ZulipClientWrapper
from .exceptions import AuthenticationError, PermissionError

logger = get_logger(__name__)


class IdentityType(Enum):
    """Types of identities supported by the system."""

    USER = "user"
    BOT = "bot"
    ADMIN = "admin"


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

    def __post_init__(self):
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
            # Admin has all capabilities
            self.capabilities = {
                "all",
                "user_management",
                "realm_settings",
                "export_data",
                "topic_delete",
                "stream_management",
                "organization_customization",
                "billing_management",
            }

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

    def close(self):
        """Close the client connection."""
        self._client = None

    def __str__(self) -> str:
        """String representation of identity."""
        return f"Identity(type={self.type.name}, email={self.email}, name={self.name})"

    def __eq__(self, other) -> bool:
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

    # Capability requirements for tool categories
    TOOL_CAPABILITIES = {
        # Core Messaging
        "messaging.message": ["send_message"],
        "messaging.search_messages": ["read_messages"],
        "messaging.edit_message": ["edit_own_messages"],
        "messaging.bulk_operations": ["bulk_read"],
        # Stream Management
        "streams.manage_streams": ["stream_management"],
        "streams.manage_topics": ["stream_management"],
        "streams.get_stream_info": ["read_messages"],
        # Event Streaming
        "events.register_events": ["stream_events"],
        "events.get_events": ["stream_events"],
        "events.listen_events": ["stream_events"],
        # User & Authentication
        "users.manage_users": ["user_management"],
        "users.switch_identity": [],  # Always allowed
        "users.manage_user_groups": ["user_management"],
        # Search & Analytics
        "search.advanced_search": ["search"],
        "search.analytics": ["read_messages"],
        # File Management
        "files.upload_file": ["upload_files"],
        "files.manage_files": ["upload_files"],
    }

    def __init__(self, config: ConfigManager):
        """Initialize identity manager with configuration.

        Args:
            config: Configuration manager with credentials
        """
        self.config = config
        self.identities: dict[IdentityType, Identity | None] = {}
        self.current_identity: IdentityType | None = None
        self._temporary_identity: IdentityType | None = None
        # Removed: _identity_stack - over-engineering with nested contexts

        # Initialize identities
        self._initialize_identities()

    def _initialize_identities(self):
        """Initialize available identities from configuration."""
        # Handle both real ConfigManager and mock objects
        # Real ConfigManager has config.config.email, mocks have config.email
        if hasattr(self.config, "config"):
            # Real ConfigManager
            email = self.config.config.email
            api_key = self.config.config.api_key
            site = self.config.config.site
            bot_email = (
                self.config.config.bot_email
                if self.config.has_bot_credentials()
                else None
            )
            bot_api_key = (
                self.config.config.bot_api_key
                if self.config.has_bot_credentials()
                else None
            )
            bot_name = (
                self.config.config.bot_name
                if hasattr(self.config.config, "bot_name")
                else "Bot"
            )
        else:
            # Mock ConfigManager (for tests)
            email = self.config.email
            api_key = self.config.api_key
            site = self.config.site
            bot_email = getattr(self.config, "bot_email", None)
            bot_api_key = getattr(self.config, "bot_api_key", None)
            bot_name = getattr(self.config, "bot_name", "Bot")

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
        has_bot = (
            self.config.has_bot_credentials()
            if hasattr(self.config, "has_bot_credentials")
            else False
        )
        if has_bot and bot_email and bot_api_key:
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

        # Admin identity will be added by _check_admin_privileges if applicable
        self._check_admin_privileges()

    def _check_admin_privileges(self):
        """Check if the user identity has admin privileges."""
        try:
            user_identity = self.identities[IdentityType.USER]
            if user_identity:
                # Try to get realm settings (admin-only endpoint)
                # Use a simpler admin-only call like get_users which should work
                result = user_identity.client.client.get_users()
                if result.get("result") == "success":
                    # User has admin access
                    admin_identity = Identity(
                        type=IdentityType.ADMIN,
                        email=user_identity.email,
                        api_key=user_identity.api_key,
                        site=user_identity.site,
                        name=f"{user_identity.name} (Admin)",
                    )
                    # Provide the config manager to admin identity
                    admin_identity._config_manager = self.config
                    self.identities[IdentityType.ADMIN] = admin_identity
                    logger.info(f"Admin privileges detected for {user_identity.email}")
        except Exception as e:
            logger.debug(f"User does not have admin privileges: {e}")

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
            # Validate by making a simple API call
            try:
                result = identity.client.get_users(request={"client_gravatar": False})
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
        """Select the best identity for a given tool.

        Args:
            tool: Tool name to execute
            preferred: Preferred identity type

        Returns:
            Best identity for the tool

        Raises:
            PermissionError: If no identity has the required capability
        """
        # If preferred identity is specified and capable, use it
        if preferred:
            if self.check_capability(tool, preferred):
                identity = self.identities.get(preferred)
                if identity:
                    return identity

        # Check current identity first
        if self.check_capability(tool):
            return self.get_current_identity()

        # Try other identities in order of preference
        preference_order = [IdentityType.USER, IdentityType.BOT, IdentityType.ADMIN]
        for identity_type in preference_order:
            if self.check_capability(tool, identity_type):
                identity = self.identities.get(identity_type)
                if identity:
                    logger.info(
                        f"Switching to {identity_type.value} identity for tool {tool}"
                    )
                    return identity

        # No identity has the required capability
        required_capabilities = self.TOOL_CAPABILITIES.get(tool, [])
        raise PermissionError(
            f"No configured identity has the required capabilities for {tool}: {required_capabilities}"
        )

    async def execute_with_identity(
        self,
        tool: str,
        params: dict[str, Any],
        executor: Callable,
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
        result = {
            "current": self.current_identity.value if self.current_identity else None,
            "temporary": (
                self._temporary_identity.value if self._temporary_identity else None
            ),
            "available": {},
        }

        for identity_type, identity in self.identities.items():
            if identity:
                result["available"][identity_type.value] = {
                    "email": identity.email,
                    "display_name": identity.display_name,
                    "name": identity.name,
                    "capabilities": list(identity.capabilities),
                    "site": identity.site,
                }

        return result

    def close_all(self):
        """Close all client connections."""
        for identity in self.identities.values():
            if identity:
                identity.close()
