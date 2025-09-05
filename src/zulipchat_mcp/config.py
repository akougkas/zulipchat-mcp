"""Configuration management for ZulipChat MCP Server."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    # Load .env file from current working directory
    load_dotenv()
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
    """Handle configuration from multiple sources with priority order."""

    def __init__(self) -> None:
        self.config = self._load_config()

    def _load_config(self) -> ZulipConfig:
        """Load configuration with priority: env vars > config file."""
        # Get configuration values
        email = self._get_email()
        api_key = self._get_api_key()
        site = self._get_site()
        debug = self._get_debug()
        port = self._get_port()

        # Bot credentials (optional)
        bot_email = self._get_bot_email()
        bot_api_key = self._get_bot_api_key()
        bot_name = self._get_bot_name()
        bot_avatar_url = self._get_bot_avatar_url()

        return ZulipConfig(
            email=email,
            api_key=api_key,
            site=site,
            debug=debug,
            port=port,
            bot_email=bot_email,
            bot_api_key=bot_api_key,
            bot_name=bot_name,
            bot_avatar_url=bot_avatar_url,
        )

    def _get_email(self) -> str:
        """Get Zulip email with fallback chain."""
        # 1. Environment variable
        if email := os.getenv("ZULIP_EMAIL"):
            return email

        # 2. Config file
        if config_data := self._load_config_file():
            if "email" in config_data:
                return config_data["email"]

        raise ValueError(
            "No Zulip email found. Please set ZULIP_EMAIL environment variable "
            "or add 'email' to your config file."
        )

    def _get_api_key(self) -> str:
        """Get Zulip API key with fallback chain."""
        # 1. Environment variable
        if key := os.getenv("ZULIP_API_KEY"):
            return key

        # 2. Config file
        if config_data := self._load_config_file():
            if "api_key" in config_data:
                return config_data["api_key"]

        raise ValueError(
            "No Zulip API key found. Please set ZULIP_API_KEY environment variable "
            "or add 'api_key' to your config file."
        )

    def _get_site(self) -> str:
        """Get Zulip site URL with fallback chain."""
        # 1. Environment variable
        if site := os.getenv("ZULIP_SITE"):
            return site

        # 2. Config file
        if config_data := self._load_config_file():
            if "site" in config_data:
                return config_data["site"]

        raise ValueError(
            "No Zulip site URL found. Please set ZULIP_SITE environment variable "
            "or add 'site' to your config file."
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

    def _load_config_file(self) -> dict[str, Any] | None:
        """Load configuration from JSON file."""
        config_path = Path.home() / ".config" / "zulipchat-mcp" / "config.json"

        if config_path.exists():
            try:
                return json.loads(config_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                if self._get_debug():
                    print(f"Warning: Could not load config from {config_path}: {e}")

        return None

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
        # 1. Environment variable
        if email := os.getenv("ZULIP_BOT_EMAIL"):
            return email

        # 2. Config file
        if config_data := self._load_config_file():
            if "bot_email" in config_data:
                return config_data["bot_email"]

        return None

    def _get_bot_api_key(self) -> str | None:
        """Get bot API key for AI agents."""
        # 1. Environment variable
        if key := os.getenv("ZULIP_BOT_API_KEY"):
            return key

        # 2. Config file
        if config_data := self._load_config_file():
            if "bot_api_key" in config_data:
                return config_data["bot_api_key"]

        return None

    def _get_bot_name(self) -> str:
        """Get bot display name."""
        # 1. Environment variable
        if name := os.getenv("ZULIP_BOT_NAME"):
            return name

        # 2. Config file
        if config_data := self._load_config_file():
            if "bot_name" in config_data:
                return config_data["bot_name"]

        return "Claude Code"

    def _get_bot_avatar_url(self) -> str | None:
        """Get bot avatar URL."""
        # 1. Environment variable
        if url := os.getenv("ZULIP_BOT_AVATAR_URL"):
            return url

        # 2. Config file
        if config_data := self._load_config_file():
            if "bot_avatar_url" in config_data:
                return config_data["bot_avatar_url"]

        return None

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
