"""Configuration management for ZulipChat MCP Server.

CLI arguments with .env fallback - matches context7 pattern.
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    from pathlib import Path

    # Load .env file from multiple locations (first found wins)
    # Priority: current directory > home directory
    env_locations = [
        Path.cwd() / ".env",  # Current working directory
        Path.home() / ".env",  # User home directory
    ]

    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    # python-dotenv not available, skip loading .env
    pass


@dataclass
class ZulipConfig:
    """Zulip configuration settings."""

    email: str
    api_key: str
    site: str
    debug: bool = False
    port: int = 3000
    # Bot credentials for AI agents
    bot_email: str | None = None
    bot_api_key: str | None = None
    bot_name: str = "Claude Code"
    bot_avatar_url: str | None = None


class ConfigManager:
    """CLI-based configuration with .env fallback for development."""

    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        site: str | None = None,
        bot_email: str | None = None,
        bot_api_key: str | None = None,
        bot_name: str | None = None,
        bot_avatar_url: str | None = None,
        debug: bool = False,
    ) -> None:
        self.config = self._load_config(
            email=email,
            api_key=api_key,
            site=site,
            bot_email=bot_email,
            bot_api_key=bot_api_key,
            bot_name=bot_name,
            bot_avatar_url=bot_avatar_url,
            debug=debug,
        )

    def _load_config(
        self,
        email: str | None = None,
        api_key: str | None = None,
        site: str | None = None,
        bot_email: str | None = None,
        bot_api_key: str | None = None,
        bot_name: str | None = None,
        bot_avatar_url: str | None = None,
        debug: bool = False,
    ) -> ZulipConfig:
        """Load configuration from CLI args with .env fallback."""
        # Priority: CLI args > environment variables > error
        final_email = email or self._get_email()
        final_api_key = api_key or self._get_api_key()
        final_site = site or self._get_site()
        final_debug = debug or self._get_debug()
        final_port = self._get_port()

        # Bot credentials (optional)
        final_bot_email = bot_email or self._get_bot_email()
        final_bot_api_key = bot_api_key or self._get_bot_api_key()
        final_bot_name = bot_name or self._get_bot_name()
        final_bot_avatar_url = bot_avatar_url or self._get_bot_avatar_url()

        return ZulipConfig(
            email=final_email,
            api_key=final_api_key,
            site=final_site,
            debug=final_debug,
            port=final_port,
            bot_email=final_bot_email,
            bot_api_key=final_bot_api_key,
            bot_name=final_bot_name,
            bot_avatar_url=final_bot_avatar_url,
        )

    def _get_email(self) -> str:
        """Get Zulip email from environment variable."""
        if email := os.getenv("ZULIP_EMAIL"):
            return email
        raise ValueError(
            "No Zulip email found. Please provide --zulip-email argument, "
            "set ZULIP_EMAIL environment variable, or create a .env file "
            "in your current directory or home directory."
        )

    def _get_api_key(self) -> str:
        """Get Zulip API key from environment variable."""
        if key := os.getenv("ZULIP_API_KEY"):
            return key
        raise ValueError(
            "No Zulip API key found. Please provide --zulip-api-key argument, "
            "set ZULIP_API_KEY environment variable, or create a .env file "
            "in your current directory or home directory."
        )

    def _get_site(self) -> str:
        """Get Zulip site URL from environment variable."""
        if site := os.getenv("ZULIP_SITE"):
            return site
        raise ValueError(
            "No Zulip site URL found. Please provide --zulip-site argument, "
            "set ZULIP_SITE environment variable, or create a .env file "
            "in your current directory or home directory."
        )

    def _get_debug(self) -> bool:
        """Get debug mode setting."""
        debug_str = os.getenv("MCP_DEBUG", "false").lower()
        return debug_str in ("true", "1", "yes", "on")

    def _get_port(self) -> int:
        """Get MCP server port."""
        try:
            return int(os.getenv("MCP_PORT", "3000"))
        except ValueError:
            return 3000

    def validate_config(self) -> bool:
        """Validate that all required configuration is present."""
        try:
            # Test that we can access all required values
            _ = self.config.email
            _ = self.config.api_key
            _ = self.config.site

            # Basic validation
            if not self.config.email or "@" not in self.config.email:
                raise ValueError("Invalid email format")

            if not self.config.api_key or len(self.config.api_key) < 10:
                raise ValueError("API key appears to be invalid")

            if not self.config.site or not (
                self.config.site.startswith("http://")
                or self.config.site.startswith("https://")
            ):
                raise ValueError("Site URL must start with http:// or https://")

            return True

        except Exception as e:
            if self.config.debug:
                print(f"Configuration validation failed: {e}")
            return False

    def _get_bot_email(self) -> str | None:
        """Get bot email for AI agents."""
        return os.getenv("ZULIP_BOT_EMAIL")

    def _get_bot_api_key(self) -> str | None:
        """Get bot API key for AI agents."""
        return os.getenv("ZULIP_BOT_API_KEY")

    def _get_bot_name(self) -> str:
        """Get bot display name."""
        return os.getenv("ZULIP_BOT_NAME", "Claude Code")

    def _get_bot_avatar_url(self) -> str | None:
        """Get bot avatar URL."""
        return os.getenv("ZULIP_BOT_AVATAR_URL")

    def has_bot_credentials(self) -> bool:
        """Check if bot credentials are configured."""
        return bool(self.config.bot_email and self.config.bot_api_key)

    def get_zulip_client_config(self, use_bot: bool = False) -> dict[str, str | None]:
        """Get configuration dict for Zulip client initialization.

        Args:
            use_bot: If True and bot credentials exist, return bot config
        """
        if (
            use_bot
            and self.has_bot_credentials()
            and self.config.bot_email
            and self.config.bot_api_key
        ):
            return {
                "email": self.config.bot_email,
                "api_key": self.config.bot_api_key,
                "site": self.config.site,
            }

        return {
            "email": self.config.email,
            "api_key": self.config.api_key,
            "site": self.config.site,
        }
