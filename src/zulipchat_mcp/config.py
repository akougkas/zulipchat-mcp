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


# Module-level singleton for ConfigManager
_config_manager: ConfigManager | None = None

# Global identity state - tracks whether to use bot or user identity
_current_identity: str = "user"  # "user" or "bot"


def init_config_manager(
    config_file: str | None = None,
    bot_config_file: str | None = None,
    debug: bool | None = None,
) -> ConfigManager:
    """Initialize the global ConfigManager singleton.

    Must be called once at server startup before any tools access config.
    Subsequent calls will reinitialize (useful for testing).

    Args:
        config_file: Path to user zuliprc file
        bot_config_file: Path to bot zuliprc file
        debug: Enable debug mode

    Returns:
        The initialized ConfigManager instance
    """
    global _config_manager
    _config_manager = ConfigManager(
        config_file=config_file,
        bot_config_file=bot_config_file,
        debug=debug,
    )
    return _config_manager


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager singleton.

    Returns:
        The ConfigManager instance

    Raises:
        RuntimeError: If init_config_manager() was not called first
    """
    if _config_manager is None:
        raise RuntimeError(
            "ConfigManager not initialized. Call init_config_manager() first."
        )
    return _config_manager


def get_current_identity() -> str:
    """Get the current identity setting ('user' or 'bot')."""
    return _current_identity


def set_current_identity(identity: str) -> None:
    """Set the current identity ('user' or 'bot')."""
    global _current_identity
    if identity not in ("user", "bot"):
        raise ValueError(f"Invalid identity: {identity}. Must be 'user' or 'bot'.")
    _current_identity = identity


def get_client():
    """Get a ZulipClientWrapper with the current identity.

    This is the canonical way to get a client - it respects the
    current identity setting from switch_identity().
    """
    from .core.client import ZulipClientWrapper

    config = get_config_manager()
    use_bot = _current_identity == "bot" and config.has_bot_credentials()
    return ZulipClientWrapper(config, use_bot_identity=use_bot)


def get_bot_client():
    """Get a ZulipClientWrapper that ALWAYS uses bot identity.

    Use this for operations that must always run as bot regardless
    of current identity setting (e.g., Agents-Channel operations).
    """
    from .core.client import ZulipClientWrapper

    config = get_config_manager()
    if not config.has_bot_credentials():
        raise ValueError("Bot credentials not configured")
    return ZulipClientWrapper(config, use_bot_identity=True)
