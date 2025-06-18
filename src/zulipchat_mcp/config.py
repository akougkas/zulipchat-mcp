"""Configuration management for ZulipChat MCP Server."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ZulipConfig:
    """Zulip configuration settings."""
    
    email: str
    api_key: str
    site: str
    debug: bool = False
    port: int = 3000


class ConfigManager:
    """Handle configuration from multiple sources with priority order."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> ZulipConfig:
        """Load configuration with priority: env vars > docker secrets > config file."""
        # Get configuration values
        email = self._get_email()
        api_key = self._get_api_key()
        site = self._get_site()
        debug = self._get_debug()
        port = self._get_port()
        
        return ZulipConfig(
            email=email,
            api_key=api_key,
            site=site,
            debug=debug,
            port=port
        )
    
    def _get_email(self) -> str:
        """Get Zulip email with fallback chain."""
        # 1. Environment variable
        if email := os.getenv('ZULIP_EMAIL'):
            return email
            
        # 2. Docker secret
        secret_path = Path('/run/secrets/zulip_email')
        if secret_path.exists():
            return secret_path.read_text().strip()
            
        # 3. Config file
        if config_data := self._load_config_file():
            if 'email' in config_data:
                return config_data['email']
        
        raise ValueError(
            "No Zulip email found. Please set ZULIP_EMAIL environment variable "
            "or add 'email' to your config file."
        )
    
    def _get_api_key(self) -> str:
        """Get Zulip API key with fallback chain."""
        # 1. Environment variable
        if key := os.getenv('ZULIP_API_KEY'):
            return key
            
        # 2. Docker secret
        secret_path = Path('/run/secrets/zulip_api_key')
        if secret_path.exists():
            return secret_path.read_text().strip()
            
        # 3. Config file
        if config_data := self._load_config_file():
            if 'api_key' in config_data:
                return config_data['api_key']
        
        raise ValueError(
            "No Zulip API key found. Please set ZULIP_API_KEY environment variable "
            "or add 'api_key' to your config file."
        )
    
    def _get_site(self) -> str:
        """Get Zulip site URL with fallback chain."""
        # 1. Environment variable
        if site := os.getenv('ZULIP_SITE'):
            return site
            
        # 2. Docker secret
        secret_path = Path('/run/secrets/zulip_site')
        if secret_path.exists():
            return secret_path.read_text().strip()
            
        # 3. Config file
        if config_data := self._load_config_file():
            if 'site' in config_data:
                return config_data['site']
        
        raise ValueError(
            "No Zulip site URL found. Please set ZULIP_SITE environment variable "
            "or add 'site' to your config file."
        )
    
    def _get_debug(self) -> bool:
        """Get debug mode setting."""
        debug_str = os.getenv('MCP_DEBUG', 'false').lower()
        return debug_str in ('true', '1', 'yes', 'on')
    
    def _get_port(self) -> int:
        """Get MCP server port."""
        try:
            return int(os.getenv('MCP_PORT', '3000'))
        except ValueError:
            return 3000
    
    def _load_config_file(self) -> Optional[Dict[str, Any]]:
        """Load configuration from JSON file."""
        config_paths = [
            Path.home() / '.config' / 'zulipchat-mcp' / 'config.json',
            Path.home() / '.zulipchat-mcp.json',
            Path.cwd() / 'config.json',
        ]
        
        for path in config_paths:
            if path.exists():
                try:
                    return json.loads(path.read_text())
                except (json.JSONDecodeError, OSError) as e:
                    # Log warning but continue to next config file
                    if self._get_debug():
                        print(f"Warning: Could not load config from {path}: {e}")
                    continue
        
        return None
    
    def validate_config(self) -> bool:
        """Validate that all required configuration is present."""
        try:
            # Test that we can access all required values
            _ = self.config.email
            _ = self.config.api_key  
            _ = self.config.site
            
            # Basic validation
            if not self.config.email or '@' not in self.config.email:
                raise ValueError("Invalid email format")
            
            if not self.config.api_key or len(self.config.api_key) < 10:
                raise ValueError("API key appears to be invalid")
            
            if not self.config.site or not (
                self.config.site.startswith('http://') or 
                self.config.site.startswith('https://')
            ):
                raise ValueError("Site URL must start with http:// or https://")
            
            return True
            
        except Exception as e:
            if self.config.debug:
                print(f"Configuration validation failed: {e}")
            return False
    
    def get_zulip_client_config(self) -> Dict[str, str]:
        """Get configuration dict for Zulip client initialization."""
        return {
            'email': self.config.email,
            'api_key': self.config.api_key,
            'site': self.config.site,
        }