"""Interactive setup wizard for ZulipChat MCP.

Scans system for zuliprc files, validates credentials, and generates
MCP client configuration for major clients.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from zulip import Client

from . import __version__

# ANSI colors for terminal output
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse setup wizard CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive setup wizard for ZulipChat MCP."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def print_header() -> None:
    """Print the wizard header."""
    print(f"\n{BLUE}{BOLD}ZulipChat MCP Setup Wizard{RESET}")
    print("=" * 48)
    print("This wizard will:")
    print("  1. Find zuliprc files on your system")
    print("  2. Validate your Zulip credentials")
    print("  3. Choose core (19) or extended (55) tool mode")
    print("  4. Generate MCP client configuration")
    print("=" * 48 + "\n")


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
        display_path: Path = path
        try:
            display_path = Path("~") / path.relative_to(Path.home())
        except ValueError:
            pass
        print(f"  {BOLD}{i}.{RESET} {display_path}")


def _is_bot_like_zuliprc(path: Path) -> bool:
    """Heuristic: detect if a zuliprc appears bot-oriented."""
    if "bot" in path.name.lower():
        return True

    try:
        content = path.read_text(errors="ignore")
    except (OSError, PermissionError):
        return False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("email="):
            email = line.split("=", 1)[1].strip().lower()
            return "bot" in email

    return False


def _identity_rank(path: Path, identity_type: str) -> int:
    """Lower rank is preferred for default selection."""
    bot_like = _is_bot_like_zuliprc(path)
    if identity_type.lower() == "user":
        return 0 if not bot_like else 1
    if identity_type.lower() == "bot":
        return 0 if bot_like else 1
    return 0


def select_identity(
    files: list[Path], identity_type: str, exclude: Path | None = None
) -> dict[str, Any] | None:
    """Let user select and validate a zuliprc for the given identity type."""
    available = [f for f in files if f != exclude]
    available.sort(key=lambda p: _identity_rank(p, identity_type))

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
        if sys.platform == "win32":
            return (
                home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
            )
        return home / ".config" / "Claude" / "claude_desktop_config.json"

    if client_type == "gemini":
        paths = [
            home / ".gemini" / "settings.json",
            home / ".config" / "google-gemini-cli" / "settings.json",
        ]
        for p in paths:
            if p.exists():
                return p
        return home / ".gemini" / "settings.json"

    if client_type == "claude-code":
        paths = [
            home / ".claude.json",
            home / ".config" / "claude-code" / "settings.json",
        ]
        for p in paths:
            if p.exists():
                return p
        return None

    if client_type == "codex":
        return home / ".codex" / "config.toml"

    if client_type == "cursor":
        return home / ".cursor" / "mcp.json"

    if client_type == "windsurf":
        return home / ".codeium" / "windsurf" / "mcp_config.json"

    if client_type == "vscode":
        return Path.cwd() / ".vscode" / "mcp.json"

    if client_type == "opencode":
        paths = [
            home / ".config" / "opencode" / "opencode.json",
            home / ".opencode" / "opencode.json",
        ]
        for p in paths:
            if p.exists():
                return p
        return home / ".config" / "opencode" / "opencode.json"

    if client_type == "antigravity":
        return home / ".gemini" / "antigravity" / "mcp_config.json"

    return None


def _build_args(
    user_config: dict[str, Any],
    bot_config: dict[str, Any] | None,
    *,
    extended_tools: bool,
    use_uvx: bool,
) -> list[str]:
    """Build MCP server command args."""
    if use_uvx:
        args = ["zulipchat-mcp", "--zulip-config-file", user_config["path"]]
    else:
        args = ["run", "zulipchat-mcp", "--zulip-config-file", user_config["path"]]

    if bot_config:
        args.extend(["--zulip-bot-config-file", bot_config["path"]])

    if extended_tools:
        args.append("--extended-tools")

    return args


def generate_mcp_config(
    user_config: dict[str, Any],
    bot_config: dict[str, Any] | None = None,
    *,
    extended_tools: bool = False,
    use_uvx: bool = False,
) -> dict[str, Any]:
    """Generate MCP server configuration."""
    command = shutil.which("uv") or "uv"
    args = _build_args(
        user_config,
        bot_config,
        extended_tools=extended_tools,
        use_uvx=use_uvx,
    )
    return {
        "command": command,
        "args": args,
    }


def generate_claude_code_command(
    user_config: dict[str, Any],
    bot_config: dict[str, Any] | None = None,
    *,
    extended_tools: bool = False,
) -> str:
    """Generate `claude mcp add` command for Claude Code."""
    parts = ["claude mcp add zulipchat"]
    parts.append(f"-e ZULIP_CONFIG_FILE={user_config['path']}")

    if bot_config:
        parts.append(f"-e ZULIP_BOT_CONFIG_FILE={bot_config['path']}")

    cmd_tail = "-- uvx zulipchat-mcp"
    if extended_tools:
        cmd_tail += " --extended-tools"
    parts.append(cmd_tail)

    return " \\\n  ".join(parts)


def write_config_to_file(
    config_path: Path,
    server_key: str,
    mcp_config: dict[str, Any],
    root_key: str = "mcpServers",
) -> bool:
    """Write MCP config to client configuration file."""
    try:
        if config_path.exists():
            backup = config_path.with_suffix(config_path.suffix + ".bak")
            shutil.copy2(config_path, backup)
            print(f"{DIM}Backup created: {backup}{RESET}")
            with open(config_path) as f:
                settings = json.load(f)
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            settings = {}

        if root_key not in settings:
            settings[root_key] = {}

        settings[root_key][server_key] = mcp_config

        with open(config_path, "w") as f:
            json.dump(settings, f, indent=2)

        print(f"{GREEN}Configuration written to {config_path}{RESET}")
        return True

    except Exception as e:
        print(f"{RED}Failed to write config: {e}{RESET}")
        return False


def _render_vscode_config(base: dict[str, Any]) -> dict[str, Any]:
    """Render VS Code/Copilot config shape."""
    return {
        "type": "stdio",
        "command": base["command"],
        "args": base["args"],
    }


def _render_opencode_config(base: dict[str, Any]) -> dict[str, Any]:
    """Render OpenCode config shape."""
    return {
        "type": "local",
        "enabled": True,
        "command": [base["command"], *base["args"]],
    }


def _print_config_block(title: str, payload: dict[str, Any]) -> None:
    """Print a formatted JSON block."""
    print(f"\n{BOLD}{title}{RESET}")
    print(json.dumps(payload, indent=2))


def _select_tool_mode() -> bool:
    """Prompt for core vs extended tool mode."""
    print(f"\n{BOLD}Step 4: Tool Mode{RESET}")
    print("  1. Core mode (19 tools, default)")
    print("  2. Extended mode (55 tools)")
    choice = prompt("Choice", default="1")
    return choice.strip() == "2"


def main(argv: list[str] | None = None) -> None:
    """Run the setup wizard."""
    _parse_args(argv)
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

    # Step 4: Core vs extended
    extended_tools = _select_tool_mode()

    # Step 5: Generate configuration
    print(f"\n{BOLD}Step 5: Generate Configuration{RESET}")
    print("Which MCP client are you configuring?")
    print("  1. Claude Code (CLI)")
    print("  2. Claude Desktop")
    print("  3. Gemini CLI")
    print("  4. Codex")
    print("  5. Cursor")
    print("  6. Windsurf")
    print("  7. VS Code / GitHub Copilot")
    print("  8. OpenCode")
    print("  9. Antigravity")
    print(" 10. Show generic JSON only")

    client_choice = prompt("Choice", default="1")

    # Use uvx-style args for generated snippets for easier distribution
    mcp_config = generate_mcp_config(
        user_config,
        bot_config,
        extended_tools=extended_tools,
        use_uvx=True,
    )

    if client_choice == "1":
        print(f"\n{BOLD}Run this command to add the MCP server:{RESET}\n")
        print(
            generate_claude_code_command(
                user_config,
                bot_config,
                extended_tools=extended_tools,
            )
        )
        print()

    elif client_choice == "2":
        config_path = get_mcp_client_config_path("claude-desktop")
        payload = {"zulipchat": mcp_config}
        _print_config_block("Claude Desktop configuration", payload)
        if config_path:
            write_to_file = prompt(f"\nWrite to {config_path}? [y/N]", default="n")
            if write_to_file.lower() == "y":
                write_config_to_file(config_path, "zulipchat", mcp_config)

    elif client_choice == "3":
        config_path = get_mcp_client_config_path("gemini")
        payload = {"mcpServers": {"zulipchat": mcp_config}}
        _print_config_block("Gemini CLI configuration", payload)
        if config_path:
            write_to_file = prompt(f"\nWrite to {config_path}? [y/N]", default="n")
            if write_to_file.lower() == "y":
                write_config_to_file(config_path, "zulipchat", mcp_config)

    elif client_choice == "4":
        config_path = get_mcp_client_config_path("codex")
        print(f"\n{BOLD}Codex configuration (config.toml){RESET}")
        args = ", ".join(f'"{arg}"' for arg in mcp_config["args"])
        print(
            f"\n[mcp_servers.zulipchat]\ncommand = \"{mcp_config['command']}\"\nargs = [{args}]\n"
        )
        if config_path:
            print(f"Suggested path: {config_path}")

    elif client_choice == "5":
        config_path = get_mcp_client_config_path("cursor")
        payload = {"mcpServers": {"zulipchat": mcp_config}}
        _print_config_block("Cursor configuration", payload)
        if config_path:
            print(f"Suggested path: {config_path}")

    elif client_choice == "6":
        config_path = get_mcp_client_config_path("windsurf")
        payload = {"mcpServers": {"zulipchat": mcp_config}}
        _print_config_block("Windsurf configuration", payload)
        if config_path:
            print(f"Suggested path: {config_path}")

    elif client_choice == "7":
        config_path = get_mcp_client_config_path("vscode")
        vscode_server = _render_vscode_config(mcp_config)
        payload = {"servers": {"zulipchat": vscode_server}}
        _print_config_block("VS Code / Copilot configuration", payload)
        if config_path:
            print(f"Suggested path: {config_path}")
            write_to_file = prompt(f"\nWrite to {config_path}? [y/N]", default="n")
            if write_to_file.lower() == "y":
                write_config_to_file(
                    config_path,
                    "zulipchat",
                    vscode_server,
                    root_key="servers",
                )

    elif client_choice == "8":
        config_path = get_mcp_client_config_path("opencode")
        opencode_server = _render_opencode_config(mcp_config)
        payload = {"mcp": {"zulipchat": opencode_server}}
        _print_config_block("OpenCode configuration", payload)
        if config_path:
            print(f"Suggested path: {config_path}")

    elif client_choice == "9":
        config_path = get_mcp_client_config_path("antigravity")
        payload = {"mcpServers": {"zulipchat": mcp_config}}
        _print_config_block("Antigravity configuration", payload)
        if config_path:
            print(f"Suggested path: {config_path}")

    else:
        payload = {"mcpServers": {"zulipchat": mcp_config}}
        _print_config_block("Generic MCP server configuration", payload)

    print(f"\n{GREEN}{BOLD}Setup Complete!{RESET}")
    print(f"\nUser: {user_config['name']} ({user_config['email']})")
    if bot_config:
        print(f"Bot:  {bot_config['name']} ({bot_config['email']})")
    print(f"Tool mode: {'Extended (55)' if extended_tools else 'Core (19)'}")
    print("\nRestart your MCP client to apply changes.")


if __name__ == "__main__":
    try:
        main()
    except EOFError:
        print("\n\nSetup wizard requires an interactive terminal.")
        print("Run it directly, not through piped stdin.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)
