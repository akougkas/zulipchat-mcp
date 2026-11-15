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

DEFAULT_ZULIPRC = Path.home() / ".zuliprc"
KNOWN_AGENTS = {
    "clio": ["clio-coder", "acp"],
    "opencode": ["opencode", "acp"],
    "goose": ["goose", "acp"],
    "gemini": ["gemini", "--acp"],
    "claude": ["claude-agent-acp"],  # npm i -g @agentclientprotocol/claude-agent-acp
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
    owner_zuliprc = args.owner_zuliprc
    if not args.bot_zuliprc and not owner_zuliprc and DEFAULT_ZULIPRC.is_file():
        owner_zuliprc = str(DEFAULT_ZULIPRC)
    if args.bot_zuliprc:
        zuliprc = Path(args.bot_zuliprc).expanduser().resolve()
    elif owner_zuliprc:
        from ..config import ConfigManager
        from ..core.client import ZulipClientWrapper
        from .provision import ProvisionError, create_agent_bot, write_bot_zuliprc

        owner = ZulipClientWrapper(
            ConfigManager(config_file=str(Path(owner_zuliprc).expanduser()))
        )
        try:
            created = create_agent_bot(
                owner, args.full_name or args.name.title(), args.short_name or args.name
            )
        except ProvisionError as error:
            print(f"Zulip refused to create the bot: {error}", file=sys.stderr)
            return 1
        write_bot_zuliprc(
            zuliprc, created["email"], created["api_key"], owner.client.base_url
        )
        print(f"Created bot {created['email']} owned by you; key saved to {zuliprc}")
    else:
        print(
            f"No {DEFAULT_ZULIPRC}. Download your zuliprc from Zulip (Settings > "
            "Account & privacy > API key), or pass --owner-zuliprc PATH, or "
            "--bot-zuliprc PATH for an existing bot.",
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
        'zulip_tools = "ask"\n'
    )
    target.chmod(0o600)
    load_agent(target)
    print(f"Wrote {target}.")
    from . import service

    if service.installed():
        try:
            service.restart()
            print(f"Restarted the bridge; DM the bot to talk to {args.name}.")
        except service.ServiceError as error:
            print(f"Could not restart the bridge: {error}", file=sys.stderr)
    else:
        print(
            "Next: zulipchat-mcp-agents service install (runs the bridge now and "
            "at login), or zulipchat-mcp-agents run in a terminal."
        )
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


async def _serve(agents: list[AgentConfig], accept_owner: bool = False) -> int:
    from .bridge import AgentBridge

    bridges = [AgentBridge(agent, accept_owner) for agent in agents]
    loop = asyncio.get_running_loop()

    def stop_all() -> None:
        for bridge in bridges:
            bridge.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_all)
    results = await asyncio.gather(*(b.run() for b in bridges), return_exceptions=True)
    failed = 0
    for agent, result in zip(agents, results, strict=True):
        if isinstance(result, Exception):
            print(f"{agent.name}: {result}", file=sys.stderr)
            failed = 1
    return failed


def cmd_run(args: argparse.Namespace) -> int:
    from ..utils.logging import setup_structured_logging

    setup_structured_logging("DEBUG" if args.debug else "INFO")
    agents = load_agents()
    if args.agent:
        agents = [a for a in agents if a.name in args.agent]
    if not agents:
        print(f"No agent bots declared in {config_dir()}", file=sys.stderr)
        return 1
    return asyncio.run(_serve(agents, args.accept_owner))


def cmd_teleport(args: argparse.Namespace) -> int:
    from .teleport import TeleportError, latest_session, teleport

    path = config_dir() / f"{args.name}.toml"
    if not path.is_file():
        print(f"No agent bot '{args.name}' in {config_dir()}", file=sys.stderr)
        return 1
    config = load_agent(path)
    workspace = Path(args.cwd).expanduser().resolve()
    try:
        session = (
            {"sessionId": args.session}
            if args.session
            else asyncio.run(latest_session(config, workspace))
        )
        session_id = str(session["sessionId"])
        title = f" ({session['title']})" if session.get("title") else ""
        message = args.message or (
            f"Continuing session `{session_id}`{title} in `{workspace}`. "
            "Reply here to carry on. Close the terminal session first, so two "
            "processes do not write the same session."
        )
        response = teleport(config, workspace, session_id, message)
    except TeleportError as error:
        print(error, file=sys.stderr)
        return 1
    if response.get("result") != "success":
        print(f"Zulip refused the message: {response.get('msg')}", file=sys.stderr)
        return 1
    print(f"{args.name} will resume {session_id}{title} in your DM with the bot.")
    return 0


def cmd_service(args: argparse.Namespace) -> int:
    from . import service

    try:
        if args.action == "install":
            if not load_agents():
                print(
                    f"No agent bots in {config_dir()}; add one first: "
                    "zulipchat-mcp-agents add claude",
                    file=sys.stderr,
                )
                return 1
            print(service.install())
        elif args.action == "uninstall":
            print(service.uninstall())
        else:
            code, text = service.status()
            print(text)
            return code
    except (service.ServiceError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
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
        "--owner-zuliprc",
        help="your own zuliprc; creates a new Generic bot you own (default ~/.zuliprc)",
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
    run.add_argument(
        "--accept-owner",
        action="store_true",
        help="pair again after you changed a bot's owner in Zulip yourself",
    )
    run.set_defaults(func=cmd_run)
    teleport = sub.add_parser(
        "teleport", help="Continue a local agent session in a DM with its bot"
    )
    teleport.add_argument("name", help="agent bot name, e.g. clio")
    teleport.add_argument(
        "--session", help="session ID (default: the newest session in --cwd)"
    )
    teleport.add_argument("--cwd", default=".", help="the session's workspace")
    teleport.add_argument("--message", help="what the bot says in the DM")
    teleport.set_defaults(func=cmd_teleport)
    service = sub.add_parser(
        "service", help="Run the bridge in the background, starting at login"
    )
    service.add_argument("action", choices=["install", "uninstall", "status"])
    service.set_defaults(func=cmd_service)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
