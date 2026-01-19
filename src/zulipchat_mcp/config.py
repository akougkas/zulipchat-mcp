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

    email: str | None
    api_key: str | None
    site: str | None
    config_file: str | None = None
    debug: bool = False
    port: int = 3000
    # Bot credentials for AI agents
    bot_email: str | None = None
    bot_api_key: str | None = None
    bot_name: str = "Claude Code"
    bot_avatar_url: str | None = None
    bot_config_file: str | None = None


class ConfigManager:
    """Configuration manager - Zuliprc First."""

    def __init__(
        self,
        config_file: str | None = None,
        bot_config_file: str | None = None,
        debug: bool | None = None,
    ) -> None:
        self.config = self._load_config(
            cli_config_file=config_file,
            cli_bot_config_file=bot_config_file,
            cli_debug=debug,
        )

    def _load_config(
        self,
        cli_config_file: str | None = None,
        cli_bot_config_file: str | None = None,
        cli_debug: bool | None = None,
    ) -> ZulipConfig:
        """Load configuration - zuliprc files only."""
        # Check environment for config file paths
        final_config_file = self._get_config_file() or cli_config_file
        final_bot_config_file = self._get_bot_config_file() or cli_bot_config_file

        # Check standard locations if not provided
        if not final_config_file:
            final_config_file = self._find_default_config()

        # Optional settings
        final_debug = self._get_debug() if cli_debug is None else cli_debug
        final_port = self._get_port()

        return ZulipConfig(
            email=os.getenv("ZULIP_EMAIL"),
            api_key=os.getenv("ZULIP_API_KEY"),
            site=os.getenv("ZULIP_SITE"),
            config_file=final_config_file,
            debug=final_debug,
            port=final_port,
            bot_email=os.getenv("ZULIP_BOT_EMAIL"),
            bot_api_key=os.getenv("ZULIP_BOT_API_KEY"),
            bot_config_file=final_bot_config_file,
        )

    def _find_default_config(self) -> str | None:
        """Search for zuliprc in standard locations."""
        import os
        from pathlib import Path

        home = Path.home()
        candidates = [
            os.path.join(os.getcwd(), "zuliprc"),
            os.path.join(home, ".zuliprc"),
            os.path.join(home, ".config", "zulip", "zuliprc"),
        ]

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _get_config_file(self) -> str | None:
        """Get Zulip config file path from environment variable."""
        return os.getenv("ZULIP_CONFIG_FILE")

    def _get_bot_config_file(self) -> str | None:
        """Get bot config file path."""
        return os.getenv("ZULIP_BOT_CONFIG_FILE")

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
        """Validate that configuration is present."""
        if self.config.config_file:
            if not os.path.exists(self.config.config_file):
                # Don't raise, just return False to let caller handle error
                return False
            return True

        # Check for environment variables
        if self.config.email and self.config.api_key and self.config.site:
            return True

        return False

    def has_bot_credentials(self) -> bool:
        """Check if bot credentials are configured."""
        if self.config.bot_config_file and os.path.exists(self.config.bot_config_file):
            return True
        return bool(self.config.bot_email and self.config.bot_api_key)

    def get_zulip_client_config(self, use_bot: bool = False) -> dict[str, str | None]:
        """Get configuration dict for Zulip client initialization."""
        if use_bot and self.has_bot_credentials():
            return {
                "email": self.config.bot_email,
                "api_key": self.config.bot_api_key,
                "site": self.config.site,  # Bot uses same site
                "config_file": self.config.bot_config_file,
            }

        return {
            "email": self.config.email,
            "api_key": self.config.api_key,
            "site": self.config.site,
            "config_file": self.config.config_file,
        }
