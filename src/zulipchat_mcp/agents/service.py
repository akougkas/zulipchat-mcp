"""Run the bridge as a per-user background service: systemd on Linux, launchd on macOS.

The service starts at login, restarts after a crash, and runs the bridge with
the interpreter of the installation that installed it. It records the
installing shell's PATH: agents such as pancode and claude-agent-acp are
Node scripts found through PATH, which a service manager does not inherit.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

NAME = "zulipchat-mcp-agents"
LABEL = "io.github.akougkas.zulipchat-mcp-agents"
# `run` exits with this status when restarting cannot help (EX_CONFIG).
CONFIG_ERROR = 78


class ServiceError(RuntimeError):
    pass


def _platform() -> str:
    if sys.platform.startswith("linux"):
        return "systemd"
    if sys.platform == "darwin":
        return "launchd"
    raise ServiceError(
        "Background service is supported on Linux (also WSL) and macOS. "
        "Elsewhere keep `zulipchat-mcp-agents run` open in a terminal."
    )


def unit_path() -> Path:
    if _platform() == "launchd":
        return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user" / f"{NAME}.service"


def command() -> list[str]:
    """The bridge command for a service, from a durable installation only."""
    if "archive-v0" in Path(sys.prefix).parts:
        # uvx runs from uv's cache, which `uv cache clean` deletes and an
        # upgrade never updates.
        raise ServiceError(
            "This is a temporary uvx environment. Install the package first: "
            "uv tool install zulipchat-mcp, then run "
            "zulipchat-mcp-agents service install"
        )
    return [sys.executable, "-m", "zulipchat_mcp.agents.cli", "run"]


def render_systemd(argv: list[str], path: str) -> str:
    quoted = " ".join(f'"{part}"' if " " in part else part for part in argv)
    return (
        "[Unit]\n"
        "Description=Zulip agent bots (zulipchat-mcp-agents)\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        f"ExecStart={quoted}\n"
        f'Environment="PATH={path}"\n'
        "Restart=on-failure\n"
        "RestartSec=10\n"
        f"RestartPreventExitStatus={CONFIG_ERROR}\n"
        # The bridge stops its agents itself; stragglers are killed after.
        "KillMode=mixed\n"
        "TimeoutStopSec=30\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def render_launchd(argv: list[str], path: str) -> bytes:
    log = str(Path.home() / "Library" / "Logs" / f"{NAME}.log")
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": argv,
            "EnvironmentVariables": {"PATH": path},
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 30,
            "StandardOutPath": log,
            "StandardErrorPath": log,
        }
    )


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise ServiceError(f"{argv[0]} is not available: {error}") from error


def _check(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise ServiceError((result.stderr or result.stdout).strip())


def _launchd_target() -> str:
    return f"gui/{os.getuid()}"


def install() -> str:
    """Write the service, start it now and at every login; return a note."""
    platform, path = _platform(), unit_path()
    argv = command()
    path.parent.mkdir(parents=True, exist_ok=True)
    if platform == "systemd":
        path.write_text(render_systemd(argv, os.environ.get("PATH", "")))
        _check(_run("systemctl", "--user", "daemon-reload"))
        _check(_run("systemctl", "--user", "enable", NAME))
        _check(_run("systemctl", "--user", "restart", NAME))
        return (
            f"Installed {path}; the bridge is running and starts at login.\n"
            f"Logs: journalctl --user -u {NAME} -f\n"
            "To keep it running while you are logged out: "
            "loginctl enable-linger $USER"
        )
    path.write_bytes(render_launchd(argv, os.environ.get("PATH", "")))
    _run("launchctl", "bootout", f"{_launchd_target()}/{LABEL}")
    _check(_run("launchctl", "bootstrap", _launchd_target(), str(path)))
    return (
        f"Installed {path}; the bridge is running and starts at login.\n"
        f"Logs: ~/Library/Logs/{NAME}.log"
    )


def uninstall() -> str:
    platform, path = _platform(), unit_path()
    if not path.exists():
        return "No service is installed."
    if platform == "systemd":
        _run("systemctl", "--user", "disable", "--now", NAME)
        path.unlink()
        _run("systemctl", "--user", "daemon-reload")
    else:
        _run("launchctl", "bootout", f"{_launchd_target()}/{LABEL}")
        path.unlink()
    return f"Stopped the bridge and removed {path}."


def installed() -> bool:
    try:
        return unit_path().exists()
    except ServiceError:
        return False


def restart() -> None:
    """Restart an installed service so it reads the agent files again."""
    if _platform() == "systemd":
        _check(_run("systemctl", "--user", "restart", NAME))
    else:
        _check(_run("launchctl", "kickstart", "-k", f"{_launchd_target()}/{LABEL}"))


def status() -> tuple[int, str]:
    if not installed():
        return 1, "No service is installed: zulipchat-mcp-agents service install"
    if _platform() == "systemd":
        result = _run("systemctl", "--user", "status", "--no-pager", "-n", "20", NAME)
    else:
        result = _run("launchctl", "print", f"{_launchd_target()}/{LABEL}")
    return result.returncode, (result.stdout or result.stderr).rstrip()
