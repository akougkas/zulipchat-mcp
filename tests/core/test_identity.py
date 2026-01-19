"""Tests for core/identity.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.config import ConfigManager, ZulipConfig
from src.zulipchat_mcp.core.identity import (
    Identity,
    IdentityManager,
    IdentityType,
)


class TestIdentity:
    """Tests for Identity class."""

    def test_init_user_capabilities(self):
        """Test user identity capabilities initialization."""
        identity = Identity(
            type=IdentityType.USER,
            email="user@example.com",
            api_key="key",
            name="Test User",
        )
        assert "send_message" in identity.capabilities
        assert "read_messages" in identity.capabilities
        assert identity.display_name == "Test User"

    def test_init_bot_capabilities(self):
        """Test bot identity capabilities initialization."""
        identity = Identity(
            type=IdentityType.BOT,
            email="bot@example.com",
            api_key="key",
            name="Test Bot",
        )
        assert "send_message" in identity.capabilities
        assert "automated_responses" in identity.capabilities

    def test_client_property_lazy_loading(self):
        """Test that client is created lazily."""
        identity = Identity(
            type=IdentityType.USER, email="user@example.com", api_key="key"
        )
        assert identity._client is None

        with patch(
            "src.zulipchat_mcp.core.identity.ZulipClientWrapper"
        ) as mock_wrapper:
            client = identity.client
            assert client is not None
            assert identity._client is not None
            mock_wrapper.assert_called_once()

    def test_has_capability(self):
        """Test checking capabilities."""
        identity = Identity(type=IdentityType.USER, email="u", api_key="k")
        # Assuming user has send_message
        assert identity.has_capability("send_message") is True
        assert identity.has_capability("non_existent_cap") is False

        # Test "all" capability
        identity.capabilities.add("all")
        assert identity.has_capability("anything") is True


class TestIdentityManager:
    """Tests for IdentityManager."""

    @pytest.fixture
    def mock_config(self):
        config_data = ZulipConfig(
            email="user@example.com",
            api_key="user_key",
            site="https://chat.zulip.org",
            bot_email="bot@example.com",
            bot_api_key="bot_key",
            bot_name="Bot",
        )
        manager = MagicMock(spec=ConfigManager)
        manager.config = config_data

        # Setup attribute access on manager (since code uses getattr(self.config, "email", ...))
        manager.email = "user@example.com"
        manager.api_key = "user_key"
        manager.site = "https://chat.zulip.org"
        manager.bot_email = "bot@example.com"
        manager.bot_api_key = "bot_key"
        manager.bot_name = "Bot"

        manager.has_bot_credentials.return_value = True
        return manager

    @pytest.fixture
    def identity_manager(self, mock_config):
        return IdentityManager(mock_config)

    def test_init_identities(self, identity_manager):
        """Test initialization of identities."""
        assert IdentityType.USER in identity_manager.identities
        assert IdentityType.BOT in identity_manager.identities
        assert identity_manager.current_identity == IdentityType.USER

    def test_get_current_identity(self, identity_manager):
        """Test getting current identity."""
        identity = identity_manager.get_current_identity()
        assert identity.type == IdentityType.USER
        assert identity.email == "user@example.com"

    def test_switch_identity_persist(self, identity_manager):
        """Test switching identity permanently."""
        # Mock client for validation
        with patch.object(Identity, "client") as mock_client:
            mock_client.get_users.return_value = {"result": "success"}

            result = identity_manager.switch_identity(IdentityType.BOT, persist=True)

            assert result["status"] == "success"
            assert identity_manager.current_identity == IdentityType.BOT
            assert identity_manager.get_current_identity().type == IdentityType.BOT

    def test_switch_identity_temp(self, identity_manager):
        """Test switching identity temporarily (via switch_identity method, not context manager)."""
        # Note: switch_identity with persist=False sets _temporary_identity
        with patch.object(Identity, "client") as mock_client:
            mock_client.get_users.return_value = {"result": "success"}

            identity_manager.switch_identity(IdentityType.BOT, persist=False)

            assert identity_manager.current_identity == IdentityType.USER
            assert identity_manager._temporary_identity == IdentityType.BOT
            # get_current_identity should prefer temporary
            assert identity_manager.get_current_identity().type == IdentityType.BOT

    @pytest.mark.asyncio
    async def test_use_identity_context_manager(self, identity_manager):
        """Test use_identity context manager."""
        assert identity_manager.get_current_identity().type == IdentityType.USER

        async with identity_manager.use_identity(IdentityType.BOT):
            assert identity_manager.get_current_identity().type == IdentityType.BOT

        assert identity_manager.get_current_identity().type == IdentityType.USER

    def test_check_capability(self, identity_manager):
        """Test checking capability."""
        # messaging.message requires send_message. User has it.
        assert identity_manager.check_capability("messaging.message") is True

        # Test nonexistent tool (returns True as no specific requirements)
        assert identity_manager.check_capability("unknown.tool") is True

        # Test with explicit identity
        assert (
            identity_manager.check_capability("messaging.message", IdentityType.USER)
            is True
        )

    def test_select_best_identity(self, identity_manager):
        """Test identity selection logic."""
        # Defaults to USER
        assert (
            identity_manager.select_best_identity("messaging.message").type
            == IdentityType.USER
        )

        # Agent tool -> BOT
        assert (
            identity_manager.select_best_identity("agent_message").type
            == IdentityType.BOT
        )

        # Explicit preference
        assert (
            identity_manager.select_best_identity(
                "messaging.message", IdentityType.BOT
            ).type
            == IdentityType.BOT
        )

    @pytest.mark.asyncio
    async def test_execute_with_identity(self, identity_manager):
        """Test executing function with identity."""
        executor = AsyncMock(return_value="done")

        result = await identity_manager.execute_with_identity(
            "test_tool", {"param": 1}, executor
        )

        assert result == "done"
        executor.assert_called_once()
        # Verify call args: (client, params)
        args, _ = executor.call_args
        assert isinstance(
            args[0], MagicMock
        )  # The client (since we didn't patch ZulipClientWrapper globally here but accessed via identity.client property which uses MagicMock if we patch it)
        # Wait, identity.client property creates a new wrapper if not set.
        # But we are mocking at instance level?
        # The test relies on `Identity.client` property creating a real wrapper if not mocked.
        # But `Identity.client` creates `ZulipClientWrapper`. Since we mocked `ZulipClientWrapper` in `test_client_property_lazy_loading` but not here, it might try to create real one.
        # We should patch `ZulipClientWrapper` in this test or fixture.

    @pytest.fixture(autouse=True)
    def mock_wrapper(self):
        with patch("src.zulipchat_mcp.core.identity.ZulipClientWrapper") as mock:
            yield mock

    def test_get_available_identities(self, identity_manager):
        """Test getting available identities."""
        info = identity_manager.get_available_identities()
        assert "user" in info["available"]
        assert "bot" in info["available"]
        assert info["current"] == "user"
