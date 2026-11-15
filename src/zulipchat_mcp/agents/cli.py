"""zulipchat-mcp-agents: declare Zulip agent bots and run the local bridge."""

from __future__ import annotations

import argparse
import asyncio
import shlex
import shutil
import signal
import sys
from pathlib import Path

from .config import AgentConfig, config_dir, load_agent, load_agents

KNOWN_AGENTS = {
    "clio": ["clio-coder", "acp"],
    "opencode": ["opencode", "acp"],
    "goose": ["goose", "acp"],
    "gemini": ["gemini", "--acp"],
    "claude": ["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
    "codex": ["npx", "-y", "@agentclientprotocol/codex-acp"],
}


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


def cmd_add(args: argparse.Namespace) -> int:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{args.name}.toml"
    if target.exists():
        print(f"{target} already exists; edit it instead.", file=sys.stderr)
        return 1
    command = shlex.split(args.command) if args.command else KNOWN_AGENTS.get(args.name)
    if not command:
        print(
            f"Pass --command for '{args.name}'; known agents: {sorted(KNOWN_AGENTS)}",
            file=sys.stderr,
        )
        return 1
    if shutil.which(command[0]) is None:
        print(f"Warning: {command[0]} is not on PATH.", file=sys.stderr)
    zuliprc = directory / f"{args.name}.zuliprc"
    if args.bot_zuliprc:
        zuliprc = Path(args.bot_zuliprc).expanduser().resolve()
    elif args.owner_zuliprc:
        from ..config import ConfigManager
        from ..core.client import ZulipClientWrapper
        from .provision import create_agent_bot, write_bot_zuliprc

        owner = ZulipClientWrapper(
            ConfigManager(config_file=str(Path(args.owner_zuliprc).expanduser()))
        )
        created = create_agent_bot(
            owner, args.full_name or args.name.title(), args.short_name or args.name
        )
        if created.get("result") != "success":
            print(f"Zulip refused to create the bot: {created.get('msg')}", file=sys.stderr)
            return 1
        write_bot_zuliprc(
            zuliprc, created["email"], created["api_key"], owner.client.base_url
        )
        print(f"Created bot {created['email']} owned by you; key saved to {zuliprc}")
    else:
        print(
            "Pass --bot-zuliprc for an existing bot, or --owner-zuliprc to create one.",
            file=sys.stderr,
        )
        return 1
    cwd = str(Path(args.cwd).expanduser().resolve())
    allowed = [str(Path(p).expanduser().resolve()) for p in args.allowed_dir] or [cwd]
    target.write_text(
        f'zuliprc = "{zuliprc}"\n'
        f"command = {_toml_list(command)}\n"
        f'cwd = "{cwd}"\n'
        f"allowed_dirs = {_toml_list(allowed)}\n"
        "allow = []\n"
        "idle_minutes = 30\n"
        "question_minutes = 30\n"
        "zulip_tools = true\n"
    )
    target.chmod(0o600)
    load_agent(target)
    print(f"Wrote {target}. Start the bridge with: zulipchat-mcp-agents run")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    status = 0
    for path in sorted(config_dir().glob("*.toml")):
        try:
            agent = load_agent(path)
        except (ValueError, OSError) as error:
            print(f"{path.stem}: INVALID {error}")
            status = 1
            continue
        found = shutil.which(agent.command[0]) is not None
        print(
            f"{agent.name}: {' '.join(agent.command)}"
            f"{'' if found else '  (command not on PATH)'}\n"
            f"  cwd {agent.cwd}; allowed {', '.join(map(str, agent.allowed_dirs))}"
        )
    return status


async def _serve(agents: list[AgentConfig]) -> None:
    from .bridge import AgentBridge

    bridges = [AgentBridge(agent) for agent in agents]
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: [b.stop() for b in bridges])
    results = await asyncio.gather(*(b.run() for b in bridges), return_exceptions=True)
    for agent, result in zip(agents, results, strict=True):
        if isinstance(result, Exception):
            print(f"{agent.name}: {result}", file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> int:
    from ..utils.logging import setup_structured_logging

    setup_structured_logging("DEBUG" if args.debug else "INFO")
    agents = load_agents()
    if args.agent:
        agents = [a for a in agents if a.name in args.agent]
    if not agents:
        print(f"No agent bots declared in {config_dir()}", file=sys.stderr)
        return 1
    asyncio.run(_serve(agents))
    return 0


def cmd_service(_: argparse.Namespace) -> int:
    executable = shutil.which("zulipchat-mcp-agents") or sys.argv[0]
    print(
        "# Save as ~/.config/systemd/user/zulipchat-mcp-agents.service, then:\n"
        "#   systemctl --user daemon-reload\n"
        "#   systemctl --user enable --now zulipchat-mcp-agents\n"
        "[Unit]\nDescription=Zulip agent bots bridge\n"
        "After=network-online.target\n\n"
        f"[Service]\nExecStart={executable} run\nRestart=on-failure\nRestartSec=10\n\n"
        "[Install]\nWantedBy=default.target"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zulipchat-mcp-agents",
        description="Pair Zulip bots with coding agents on this machine over ACP.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Declare an agent bot")
    add.add_argument("name", help=f"lowercase name, e.g. {', '.join(KNOWN_AGENTS)}")
    add.add_argument("--command", help="ACP launch command (default for known names)")
    add.add_argument("--cwd", default="~", help="default workspace")
    add.add_argument("--allowed-dir", action="append", default=[])
    add.add_argument("--bot-zuliprc", help="zuliprc of an existing Generic bot")
    add.add_argument(
        "--owner-zuliprc", help="your own zuliprc; creates a new Generic bot you own"
    )
    add.add_argument("--full-name", help="bot display name when creating it")
    add.add_argument("--short-name", help="bot username part when creating it")
    add.set_defaults(func=cmd_add)
    sub.add_parser("list", help="Validate and list agent bots").set_defaults(
        func=cmd_list
    )
    run = sub.add_parser("run", help="Serve agent bots until stopped")
    run.add_argument("--agent", action="append", help="serve only these names")
    run.add_argument("--debug", action="store_true")
    run.set_defaults(func=cmd_run)
    sub.add_parser("service", help="Print a systemd user unit").set_defaults(
        func=cmd_service
    )
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
