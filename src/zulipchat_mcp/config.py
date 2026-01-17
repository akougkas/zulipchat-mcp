"""Configuration management for ZulipChat MCP Server.

Environment-first configuration following MCP standards.
"""

import os
from dataclasses import dataclass

try:
    from pathlib import Path

    from dotenv import load_dotenv

    # Load .env file for development (only current directory)
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
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
    """Environment-first configuration following MCP standards."""

    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        site: str | None = None,
        bot_email: str | None = None,
        bot_api_key: str | None = None,
        bot_name: str | None = None,
        bot_avatar_url: str | None = None,
        debug: bool | None = None,
    ) -> None:
        # Environment-first: env vars take priority, CLI args are fallback
        self.config = self._load_config(
            cli_email=email,
            cli_api_key=api_key,
            cli_site=site,
            cli_bot_email=bot_email,
            cli_bot_api_key=bot_api_key,
            cli_bot_name=bot_name,
            cli_bot_avatar_url=bot_avatar_url,
            cli_debug=debug,
        )

    def _load_config(
        self,
        cli_email: str | None = None,
        cli_api_key: str | None = None,
        cli_site: str | None = None,
        cli_bot_email: str | None = None,
        cli_bot_api_key: str | None = None,
        cli_bot_name: str | None = None,
        cli_bot_avatar_url: str | None = None,
        cli_debug: bool | None = None,
    ) -> ZulipConfig:
        """Load configuration - environment first, CLI fallback."""
        # MCP standard: Environment variables take priority
        final_email = self._get_email() or cli_email
        final_api_key = self._get_api_key() or cli_api_key
        final_site = self._get_site() or cli_site

        # Validate required fields
        if not final_email:
            raise ValueError(self._format_error("ZULIP_EMAIL", "email address"))
        if not final_api_key:
            raise ValueError(self._format_error("ZULIP_API_KEY", "API key"))
        if not final_site:
            raise ValueError(self._format_error("ZULIP_SITE", "site URL"))

        # Optional settings
        final_debug = self._get_debug() if cli_debug is None else cli_debug
        final_port = self._get_port()

        # Bot credentials (optional)
        final_bot_email = self._get_bot_email() or cli_bot_email
        final_bot_api_key = self._get_bot_api_key() or cli_bot_api_key
        final_bot_name = self._get_bot_name() or cli_bot_name or "Claude Code"
        final_bot_avatar_url = self._get_bot_avatar_url() or cli_bot_avatar_url

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

    def _format_error(self, env_var: str, description: str) -> str:
        """Format helpful error message for missing configuration."""
        return f"""\nMissing required configuration: {env_var}

To configure ZulipChat MCP, you need to provide your {description}.

Option 1: Set environment variable (recommended for Claude Code)
  export {env_var}=<your-value>

Option 2: Create .env file in current directory
  echo "{env_var}=<your-value>" >> .env

Option 3: Use command line argument (for testing)
  uv run zulipchat-mcp --{env_var.lower().replace('_', '-')} <your-value>

Get your Zulip credentials:
  1. Go to your Zulip settings: https://your-org.zulipchat.com/#settings/account-and-privacy
  2. Click "Show/change your API key"
  3. Copy your email and API key
"""

    def _get_email(self) -> str | None:
        """Get Zulip email from environment variable."""
        return os.getenv("ZULIP_EMAIL")

    def _get_api_key(self) -> str | None:
        """Get Zulip API key from environment variable."""
        return os.getenv("ZULIP_API_KEY")

    def _get_site(self) -> str | None:
        """Get Zulip site URL from environment variable."""
        return os.getenv("ZULIP_SITE")

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

    def _get_bot_name(self) -> str | None:
        """Get bot display name."""
        return os.getenv("ZULIP_BOT_NAME")

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
