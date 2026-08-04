"""CLI entry point -- interactive REPL for j-agent.

Run with:  j-agent   (after install)  or  python -m src

Commands:
    /help    Show available commands
    /tools   List registered tools
    /exit    Quit the agent
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from src.agent import Agent
from src.config import Config
from src.llm.factory import create_provider
from src.memory.context_manager import ContextManager, ContextManagerConfig
from src.memory.conversation import Session
from src.memory.token_counter import create_token_counter
from src.tools.base import ToolRegistry
from src.tools.discovery import discover_builtin_tools

BANNER = r"""
       _              _
      | |            | |
      | | ___  ___ __| |
  _   | |/ _ \/ __/ _` |
 | |__| |  __/ (_| (_| |
  \____/ \___|\___\__,_|

  Harness Engineering Practice Agent
"""


def build_tools() -> ToolRegistry:
    """Create the tool registry with all built-in tools auto-discovered."""
    registry = ToolRegistry()
    for tool in discover_builtin_tools():
        registry.register(tool)
    return registry


def create_agent(config: Config | None = None) -> Agent:
    """Create an agent with default config and tools."""
    cfg = config or Config.from_env()
    provider = create_provider(cfg)
    tools = build_tools()
    console = Console()

    # Create context manager for context window management.
    token_counter = create_token_counter(cfg.provider, cfg.model)
    ctx_config = ContextManagerConfig(
        max_context_tokens=cfg.max_context_tokens,
        compress_ratio=cfg.compress_ratio,
        summary_ratio=cfg.summary_ratio,
    )
    context_manager = ContextManager(token_counter, provider, ctx_config)

    def on_event(event: str, data: dict) -> None:
        if event == "tool_call":
            console.print(
                Panel(
                    Syntax(
                        _format_arguments(data["arguments"]),
                        "json",
                        theme="monokai",
                        word_wrap=True,
                    ),
                    title=f"[bold yellow]tool[/] {data['name']}",
                    border_style="yellow",
                )
            )
        elif event == "tool_result":
            style = "red" if data["is_error"] else "green"
            console.print(
                Panel(
                    data["content"],
                    title=f"[bold {style}]result[/] {data['name']}",
                    border_style=style,
                )
            )
        elif event == "context_managed":
            console.print(
                f"[dim]上下文已管理: {data['before_count']} -> "
                f"{data['after_count']} 条消息[/]"
            )

    return Agent(
        config=cfg,
        provider=provider,
        tools=tools,
        on_event=on_event,
        context_manager=context_manager,
    )


def _format_arguments(args: dict) -> str:
    """Format tool arguments as pretty JSON."""
    import json

    return json.dumps(args, indent=2, ensure_ascii=False)


def main() -> None:
    """Entry point for the j-agent CLI."""
    console = Console()

    try:
        config = Config.from_env()
    except RuntimeError as e:
        console.print(f"[bold red]Config error:[/] {e}")
        console.print(
            "\nCreate a [bold].env[/] file with:\n"
            "  J_AGENT_PROVIDER=claude\n"
            "  J_AGENT_API_KEY=your-api-key\n"
            "\nOptional:\n"
            "  J_AGENT_BASE_URL=https://custom-endpoint\n"
            "  J_AGENT_MODEL=claude-sonnet-4-20250514\n"
        )
        sys.exit(1)

    agent = create_agent(config)

    console.print(BANNER, style="bold cyan")
    console.print(
        f"  Provider: [bold]{config.provider}[/]  "
        f"Model: [bold]{config.model}[/]\n"
        f"  Tools: {', '.join(agent.tools.names())}\n"
        f"  Type [bold]/help[/] for commands, [bold]/exit[/] to quit.\n"
    )

    while True:
        try:
            user_input = console.input("[bold green]user>[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle slash commands.
        if user_input.startswith("/"):
            if _handle_command(user_input, agent, console):
                break
            continue

        # Normal conversation turn.
        try:
            response = agent.run(user_input)
            console.print(
                Panel(
                    response,
                    title="[bold blue]assistant[/]",
                    border_style="blue",
                )
            )
        except Exception as e:
            console.print(f"[bold red]Error:[/] {type(e).__name__}: {e}")


def _handle_command(command: str, agent: Agent, console: Console) -> bool:
    """Handle a slash command. Returns True if the agent should exit."""
    cmd = command.lower()
    parts = command.split(maxsplit=1)

    if cmd in ("/exit", "/quit", "/q"):
        console.print("[dim]Goodbye![/]")
        return True

    if cmd == "/help":
        console.print(
            Panel(
                "[bold]/help[/]      Show this help\n"
                "[bold]/tools[/]     List registered tools\n"
                "[bold]/sessions[/]  List saved sessions\n"
                "[bold]/save[/]      Save current conversation\n"
                "[bold]/load[/] <id> Load a saved session\n"
                "[bold]/exit[/]      Quit the agent",
                title="Commands",
                border_style="cyan",
            )
        )
        return False

    if cmd == "/tools":
        specs = agent.tools.to_specs()
        lines = []
        for spec in specs:
            lines.append(f"  [bold]{spec.name}[/] - {spec.description}")
        console.print(
            Panel(
                "\n".join(lines) or "  No tools registered.",
                title=f"Registered Tools ({len(specs)})",
                border_style="cyan",
            )
        )
        return False

    if cmd == "/sessions":
        sessions = Session.list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions.[/]")
            return False
        lines = []
        for s in sessions:
            lines.append(
                f"  [bold]{s['id'][:8]}[/]  "
                f"msgs: {s['message_count']}  "
                f"updated: {s['updated_at'][:19]}"
            )
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Saved Sessions ({len(sessions)})",
                border_style="cyan",
            )
        )
        return False

    if cmd == "/save":
        session = Session.from_messages(agent.messages)
        path = session.save()
        console.print(f"[dim]Session saved: {session.id}[/]")
        return False

    if parts[0].lower() == "/load" and len(parts) > 1:
        session_id = parts[1].strip()
        try:
            session = Session.load(session_id)
        except FileNotFoundError as e:
            console.print(f"[bold red]Error:[/] {e}")
            return False
        agent._messages = session.messages
        console.print(
            f"[dim]Loaded session {session.id} "
            f"({len(session.messages)} messages)[/]"
        )
        return False

    console.print(f"[dim]Unknown command: {command} (try /help)[/]")
    return False


if __name__ == "__main__":
    main()
