"""Interactive setup wizard for ZulipChat MCP.

Scans system for zuliprc files, validates credentials, and generates
MCP client configuration for Claude Desktop, Gemini CLI, or Claude Code.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from zulip import Client

# ANSI colors for terminal output
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header() -> None:
    """Print the wizard header."""
    print(f"\n{BLUE}{BOLD}ZulipChat MCP Setup Wizard{RESET}")
    print("=" * 40)
    print("This wizard will:")
    print("  1. Find zuliprc files on your system")
    print("  2. Validate your Zulip credentials")
    print("  3. Generate MCP client configuration")
    print("=" * 40 + "\n")


def prompt(question: str, default: str | None = None) -> str:
    """Prompt user for input."""
    if default:
        user_input = input(f"{question} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{question}: ").strip()


def scan_for_zuliprc_files() -> list[Path]:
    """Scan system for potential zuliprc files."""
    found: list[Path] = []
    home = Path.home()

    # Standard locations (highest priority)
    standard_paths = [
        Path.cwd() / "zuliprc",
        home / ".zuliprc",
        home / ".config" / "zulip" / "zuliprc",
    ]

    for path in standard_paths:
        if path.exists() and path.is_file():
            found.append(path)

    # Glob patterns for named zuliprc files
    patterns = [
        (home, ".zuliprc-*"),
        (home, "*zuliprc*"),
        (home / ".config", "**/zuliprc*"),
        (home / ".config" / "zulip", "*"),
        (home / "Downloads", "*zuliprc*"),
    ]

    for base_dir, pattern in patterns:
        if base_dir.exists():
            try:
                for match in base_dir.glob(pattern):
                    if match.is_file() and match not in found:
                        # Validate it looks like a zuliprc (has [api] section)
                        try:
                            content = match.read_text(errors="ignore")[:500]
                            if "[api]" in content.lower():
                                found.append(match)
                        except (OSError, PermissionError):
                            continue
            except (OSError, PermissionError):
                continue

    # Sort by modification time (newest first)
    found.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return found


def validate_zuliprc(path: Path, silent: bool = False) -> dict[str, Any] | None:
    """Validate a zuliprc file by attempting to connect."""
    if not path.exists():
        if not silent:
            print(f"{RED}File not found: {path}{RESET}")
        return None

    if not silent:
        print(f"{DIM}Testing {path}...{RESET}", end=" ", flush=True)

    try:
        client = Client(config_file=str(path))
        result = client.get_profile()

        if result.get("result") == "success":
            user_name = result.get("full_name", "Unknown")
            user_email = result.get("email", "unknown")
            is_bot = result.get("is_bot", False)

            if not silent:
                identity = "Bot" if is_bot else "User"
                print(f"{GREEN}OK{RESET} - {identity}: {user_name}")

            return {
                "path": str(path.resolve()),
                "email": user_email,
                "name": user_name,
                "is_bot": is_bot,
            }
        else:
            if not silent:
                print(f"{RED}Failed{RESET} - {result.get('msg', 'Unknown error')}")
            return None

    except Exception as e:
        if not silent:
            print(f"{RED}Error{RESET} - {e}")
        return None


def display_found_files(files: list[Path]) -> None:
    """Display found zuliprc files with indices."""
    print(f"\n{BOLD}Found {len(files)} zuliprc file(s):{RESET}\n")
    for i, path in enumerate(files, 1):
        # Show relative path if under home
        display_path = path
        try:
            display_path = path.relative_to(Path.home())
            display_path = Path("~") / display_path
        except ValueError:
            pass
        print(f"  {BOLD}{i}.{RESET} {display_path}")


def select_identity(
    files: list[Path], identity_type: str, exclude: Path | None = None
) -> dict[str, Any] | None:
    """Let user select and validate a zuliprc for the given identity type."""
    available = [f for f in files if f != exclude]

    if not available:
        print(
            f"\n{YELLOW}No additional zuliprc files available for {identity_type}.{RESET}"
        )
        manual = prompt(
            f"Enter path to {identity_type} zuliprc (or press Enter to skip)"
        )
        if manual:
            path = Path(manual).expanduser()
            return validate_zuliprc(path)
        return None

    print(f"\n{BOLD}Select {identity_type} identity:{RESET}")
    for i, path in enumerate(available, 1):
        try:
            display = Path("~") / path.relative_to(Path.home())
        except ValueError:
            display = path
        print(f"  {i}. {display}")
    print(f"  {len(available) + 1}. Enter path manually")
    print(f"  {len(available) + 2}. Skip")

    while True:
        choice = prompt("Choice", default="1")
        try:
            idx = int(choice)
            if 1 <= idx <= len(available):
                result = validate_zuliprc(available[idx - 1])
                if result:
                    return result
                retry = prompt("Try another? [y/N]", default="n")
                if retry.lower() != "y":
                    return None
            elif idx == len(available) + 1:
                manual = prompt(f"Path to {identity_type} zuliprc")
                if manual:
                    return validate_zuliprc(Path(manual).expanduser())
                return None
            elif idx == len(available) + 2:
                return None
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a number")


def get_mcp_client_config_path(client_type: str) -> Path | None:
    """Get configuration file path for the given MCP client."""
    home = Path.home()

    if client_type == "claude-desktop":
        if sys.platform == "darwin":
            return (
                home
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )
        elif sys.platform == "win32":
            return (
                home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
            )
        else:
            return home / ".config" / "Claude" / "claude_desktop_config.json"

    elif client_type == "gemini":
        paths = [
            home / ".gemini" / "settings.json",
            home / ".config" / "google-gemini-cli" / "settings.json",
        ]
        for p in paths:
            if p.exists():
                return p
        # Return default if none exist
        return home / ".gemini" / "settings.json"

    elif client_type == "claude-code":
        # Claude Code uses ~/.claude/claude_code_config.json or settings
        paths = [
            home / ".claude.json",
            home / ".config" / "claude-code" / "settings.json",
        ]
        for p in paths:
            if p.exists():
                return p
        return None

    return None


def generate_mcp_config(
    user_config: dict[str, Any],
    bot_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate MCP server configuration."""
    # Find uv path
    uv_path = shutil.which("uv") or "uv"

    args = ["run", "zulipchat-mcp", "--zulip-config-file", user_config["path"]]

    if bot_config:
        args.extend(["--zulip-bot-config-file", bot_config["path"]])

    return {
        "command": uv_path,
        "args": args,
    }


def generate_claude_code_command(
    user_config: dict[str, Any],
    bot_config: dict[str, Any] | None = None,
) -> str:
    """Generate claude mcp add command for Claude Code."""
    parts = ["claude mcp add zulipchat"]

    # Add environment variables pointing to config files
    parts.append(f"-e ZULIP_CONFIG_FILE={user_config['path']}")

    if bot_config:
        parts.append(f"-e ZULIP_BOT_CONFIG_FILE={bot_config['path']}")

    parts.append("-- uvx zulipchat-mcp")

    return " \\\n  ".join(parts)


def write_config_to_file(
    config_path: Path,
    server_key: str,
    mcp_config: dict[str, Any],
) -> bool:
    """Write MCP config to client configuration file."""
    try:
        # Create backup
        if config_path.exists():
            backup = config_path.with_suffix(".json.bak")
            shutil.copy2(config_path, backup)
            print(f"{DIM}Backup created: {backup}{RESET}")

            with open(config_path) as f:
                settings = json.load(f)
        else:
            # Create parent directories
            config_path.parent.mkdir(parents=True, exist_ok=True)
            settings = {}

        # Ensure mcpServers exists
        if "mcpServers" not in settings:
            settings["mcpServers"] = {}

        settings["mcpServers"][server_key] = mcp_config

        with open(config_path, "w") as f:
            json.dump(settings, f, indent=2)

        print(f"{GREEN}Configuration written to {config_path}{RESET}")
        return True

    except Exception as e:
        print(f"{RED}Failed to write config: {e}{RESET}")
        return False


def main() -> None:
    """Run the setup wizard."""
    print_header()

    # Step 1: Scan for zuliprc files
    print(f"{BOLD}Step 1: Scanning for zuliprc files...{RESET}")
    found_files = scan_for_zuliprc_files()

    if found_files:
        display_found_files(found_files)
    else:
        print(f"{YELLOW}No zuliprc files found automatically.{RESET}")
        print("\nDownload your zuliprc from:")
        print("  Zulip -> Settings -> Personal settings -> Account & privacy")
        print("  -> API key -> Download zuliprc")

    # Step 2: Select User identity
    print(f"\n{BOLD}Step 2: Configure User Identity{RESET}")
    print("The User identity is used for reading messages and search.")

    user_config = select_identity(found_files, "User")
    if not user_config:
        manual = prompt("\nEnter path to your zuliprc file")
        if manual:
            user_config = validate_zuliprc(Path(manual).expanduser())
        if not user_config:
            print(f"\n{RED}Cannot continue without User credentials.{RESET}")
            return

    # Step 3: Optionally select Bot identity
    print(f"\n{BOLD}Step 3: Configure Bot Identity (Optional){RESET}")
    print("A Bot identity allows the AI to send messages on behalf of a bot account.")
    setup_bot = prompt("Configure a Bot identity? [y/N]", default="n")

    bot_config = None
    if setup_bot.lower() == "y":
        bot_config = select_identity(
            found_files, "Bot", exclude=Path(user_config["path"])
        )

    # Step 4: Generate configuration
    print(f"\n{BOLD}Step 4: Generate Configuration{RESET}")
    print("Which MCP client are you configuring?")
    print("  1. Claude Code (CLI)")
    print("  2. Claude Desktop")
    print("  3. Gemini CLI")
    print("  4. Show JSON only")

    client_choice = prompt("Choice", default="1")

    mcp_config = generate_mcp_config(user_config, bot_config)

    if client_choice == "1":
        # Claude Code - show claude mcp add command
        print(f"\n{BOLD}Run this command to add the MCP server:{RESET}\n")
        print(generate_claude_code_command(user_config, bot_config))
        print()

    elif client_choice == "2":
        # Claude Desktop
        config_path = get_mcp_client_config_path("claude-desktop")
        if config_path:
            print(f"\n{BOLD}Configuration:{RESET}")
            print(json.dumps({"zulipchat": mcp_config}, indent=2))
            write_to_file = prompt(f"\nWrite to {config_path}? [y/N]", default="n")
            if write_to_file.lower() == "y":
                write_config_to_file(config_path, "zulipchat", mcp_config)
        else:
            print(f"\n{YELLOW}Could not determine Claude Desktop config path.{RESET}")
            print(json.dumps({"zulipchat": mcp_config}, indent=2))

    elif client_choice == "3":
        # Gemini CLI
        config_path = get_mcp_client_config_path("gemini")
        if config_path:
            print(f"\n{BOLD}Configuration:{RESET}")
            print(json.dumps({"zulip": mcp_config}, indent=2))
            write_to_file = prompt(f"\nWrite to {config_path}? [y/N]", default="n")
            if write_to_file.lower() == "y":
                write_config_to_file(config_path, "zulip", mcp_config)
        else:
            print(json.dumps({"zulip": mcp_config}, indent=2))

    else:
        # Just show JSON
        print(f"\n{BOLD}MCP Server Configuration:{RESET}")
        print(json.dumps({"zulipchat": mcp_config}, indent=2))

    # Summary
    print(f"\n{GREEN}{BOLD}Setup Complete!{RESET}")
    print(f"\nUser: {user_config['name']} ({user_config['email']})")
    if bot_config:
        print(f"Bot:  {bot_config['name']} ({bot_config['email']})")
    print("\nRestart your MCP client to apply changes.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)
