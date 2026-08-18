"""CLI entry point -- interactive REPL for j-agent.

Run with:  j-agent   (after install)  or  python -m src

Commands:
    /help    Show available commands
    /tools   List registered tools
    /exit    Quit the agent
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from src.agent import Agent
from src.config import CONTEXT_FILE, Config, load_work_context
from src.llm.factory import create_provider
from src.memory.context_manager import ContextManager, ContextManagerConfig
from src.memory.conversation import Session
from src.memory.token_counter import create_token_counter
from src.observability.tracer import Tracer
from src.permission.manager import PermissionManager, PermissionMode
from src.permission.risk import RiskLevel
from src.planning.plan import Plan
from src.planning.subagent import SubAgentRunner
from src.skills.discovery import discover_skills
from src.tools.base import ToolRegistry
from src.tools.builtin.plan import PlanTool
from src.tools.builtin.spawn import SpawnAgentTool
from src.tools.discovery import discover_builtin_tools
from src.work_context import WorkContext

BANNER = r"""
       _              _
      | |            | |
      | | ___  ___ __| |
  _   | |/ _ \/ __/ _` |
 | |__| |  __/ (_| (_| |
  \____/ \___|\___\__,_|

  Harness Engineering Practice Agent
"""


def build_tools(
    work_dir: Path | None = None,
    plan: Plan | None = None,
    runner: SubAgentRunner | None = None,
) -> ToolRegistry:
    """Create the tool registry with all built-in tools auto-discovered.

    Optionally injects a shared ``Plan`` into the PlanTool and a
    ``SubAgentRunner`` into the SpawnAgentTool.
    """
    registry = ToolRegistry(work_dir=work_dir)
    for tool in discover_builtin_tools():
        if isinstance(tool, PlanTool) and plan is not None:
            tool.plan = plan
        if isinstance(tool, SpawnAgentTool) and runner is not None:
            tool.runner = runner
        registry.register(tool)
    return registry


def _subagent_tools_factory(work_dir: Path | None):
    """Return a factory that builds a tool set for sub-agents.

    Sub-agents get all built-in tools except ``spawn_agent`` to prevent
    unbounded nested spawning.
    """

    def factory() -> ToolRegistry:
        registry = ToolRegistry(work_dir=work_dir)
        for tool in discover_builtin_tools():
            if isinstance(tool, SpawnAgentTool):
                continue
            registry.register(tool)
        return registry

    return factory


def create_agent(
    config: Config | None = None,
    ctx: WorkContext | None = None,
    tracer: Tracer | None = None,
    debug: bool = False,
) -> Agent:
    """Create an agent with default config, tools, and observability hooks."""
    cfg = config or Config.from_env()
    provider = create_provider(cfg)
    work_dir = ctx.work_dir if ctx else None
    plan = Plan()
    tools = build_tools(work_dir=work_dir, plan=plan)
    console = Console()

    # Create context manager for context window management.
    token_counter = create_token_counter(cfg.provider, cfg.model)
    ctx_config = ContextManagerConfig(
        max_context_tokens=cfg.max_context_tokens,
        compress_ratio=cfg.compress_ratio,
        summary_ratio=cfg.summary_ratio,
    )
    context_manager = ContextManager(token_counter, provider, ctx_config)

    # Create permission manager gating tool execution.
    permission_manager = PermissionManager(
        mode=cfg.permission_mode,
        risk_map=tools.risk_levels(),
        ask_callback=_ask_permission(console),
    )

    # Create the sub-agent runner and inject it into the spawn tool.
    runner = SubAgentRunner(
        provider=provider,
        config=cfg,
        tools_factory=_subagent_tools_factory(work_dir),
        permission_manager=permission_manager,
    )
    for tool_name in tools.names():
        tool = tools.get(tool_name)
        if isinstance(tool, SpawnAgentTool):
            tool.runner = runner

    def on_event(event: str, data: dict) -> None:
        if event == "llm_request" and debug:
            console.print(
                Panel(
                    f"[bold]model[/]: {data['model']}\n"
                    f"[bold]messages[/]: {data['message_count']}\n"
                    f"[bold]tools[/]: {', '.join(data['tool_names']) or '-'}",
                    title="[bold magenta]llm request[/]",
                    border_style="magenta",
                )
            )
            console.print(
                Syntax(
                    json.dumps(data["messages"], indent=2, ensure_ascii=False),
                    "json",
                    theme="monokai",
                    word_wrap=True,
                )
            )
        elif event == "llm_response" and debug:
            console.print(
                Panel(
                    Syntax(
                        json.dumps(
                            {
                                "content": data["content"],
                                "tool_calls": data["tool_calls"],
                                "usage": data["usage"],
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        "json",
                        theme="monokai",
                        word_wrap=True,
                    ),
                    title="[bold magenta]llm response[/]",
                    border_style="magenta",
                )
            )
        elif event == "tool_call":
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
        elif event == "permission_denied":
            console.print(
                Panel(
                    data["reason"],
                    title=f"[bold red]permission denied[/] {data['name']}",
                    border_style="red",
                )
            )

    return Agent(
        config=cfg,
        provider=provider,
        tools=tools,
        on_event=on_event,
        context_manager=context_manager,
        permission_manager=permission_manager,
        tracer=tracer,
    )


def _ask_permission(console: Console):
    """Build an interactive confirmation callback for the permission manager."""
    style_map = {
        RiskLevel.SAFE: "green",
        RiskLevel.CONFIRM: "yellow",
        RiskLevel.DANGEROUS: "red",
    }

    def ask(tool_name: str, arguments: dict, risk_level: str) -> bool:
        style = style_map.get(risk_level, "yellow")
        console.print(
            Panel(
                Syntax(
                    _format_arguments(arguments),
                    "json",
                    theme="monokai",
                    word_wrap=True,
                ),
                title=f"[bold {style}]{risk_level}[/] [bold]{tool_name}[/]",
                border_style=style,
            )
        )
        answer = console.input(
            f"[bold {style}]允许执行该操作?[/] [y/N] "
        ).strip().lower()
        return answer in ("y", "yes")

    return ask


def _format_arguments(args: dict) -> str:
    """Format tool arguments as pretty JSON."""
    return json.dumps(args, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the j-agent CLI."""
    parser = argparse.ArgumentParser(
        prog="j-agent",
        description="Harness Engineering Practice Agent",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="实时显示完整的 LLM 请求/响应",
    )
    parser.add_argument(
        "--trace",
        type=Path,
        metavar="FILE",
        help="执行轨迹写入 JSONL 文件",
    )
    args = parser.parse_args(argv)

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

    tracer = Tracer(trace_file=args.trace)
    ctx = WorkContext.from_cwd()
    agent = create_agent(config, ctx, tracer=tracer, debug=args.debug)
    skills = discover_skills(ctx.skills_dir)

    console.print(BANNER, style="bold cyan")
    console.print(
        f"  Provider: [bold]{config.provider}[/]  "
        f"Model: [bold]{config.model}[/]\n"
        f"  Work dir: [bold]{ctx.work_dir}[/]\n"
        f"  Tools: {', '.join(agent.tools.names())}\n"
        f"  Permission: [bold]{config.permission_mode}[/]\n"
        + (
            f"  Context: [bold]{CONTEXT_FILE}[/] loaded\n"
            if load_work_context()
            else ""
        )
        + (
            f"  Skills: {', '.join(s.name for s in skills)}\n"
            if skills
            else ""
        )
        + f"  Type [bold]/help[/] for commands, [bold]/exit[/] to quit.\n"
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
            if _handle_command(
                user_input, agent, console, ctx.sessions_dir, ctx.skills_dir
            ):
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

    _print_summary(console, tracer)


def _print_summary(console: Console, tracer: Tracer | None) -> None:
    """Print a session-end usage/cost summary if any calls were made."""
    if tracer is None or tracer.llm_calls == 0:
        return
    s = tracer.summary()
    console.print(
        Panel(
            f"[bold]LLM 调用[/]: {s['llm_calls']}\n"
            f"[bold]工具调用[/]: {s['tool_calls']}\n"
            f"[bold]输入 tokens[/]: {s['input_tokens']}\n"
            f"[bold]输出 tokens[/]: {s['output_tokens']}\n"
            f"[bold]总花费[/]: ${s['total_cost_usd']}",
            title="会话统计",
            border_style="cyan",
        )
    )


def _handle_command(
    command: str,
    agent: Agent,
    console: Console,
    sessions_dir: Path | None = None,
    skills_dir: Path | None = None,
) -> bool:
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
                "[bold]/skills[/]    List available skills\n"
                "[bold]/plan[/]      View current task plan\n"
                "[bold]/permission[/] [mode]  Show or set permission mode (auto/ask/yolo)\n"
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

    if cmd == "/plan":
        tasks = agent.plan.list_tasks()
        if not tasks:
            console.print("[dim]暂无任务。[/]")
            return False
        lines = [f"  [[bold]{t.status}[/]] [{t.id}] {t.title}" for t in tasks]
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Plan Tasks ({len(tasks)})",
                border_style="cyan",
            )
        )
        return False

    if cmd == "/skills":
        skills = discover_skills(skills_dir)
        if not skills:
            console.print("[dim]No skills available.[/]")
            return False
        lines = []
        for skill in skills:
            desc = skill.description.split("\n")[0]
            lines.append(f"  [bold]{skill.name}[/] - {desc}")
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Available Skills ({len(skills)})",
                border_style="cyan",
            )
        )
        return False

    if parts[0].lower() == "/permission":
        manager = agent.permission_manager
        if manager is None:
            console.print("[dim]权限系统未启用。[/]")
            return False
        if len(parts) > 1:
            new_mode = parts[1].strip().lower()
            if new_mode not in PermissionMode.ALL:
                console.print(
                    f"[bold red]无效模式:[/] {new_mode}（可选: auto / ask / yolo）"
                )
                return False
            manager.mode = new_mode
            console.print(f"[dim]权限模式已切换为: [bold]{new_mode}[/][/]")
            return False
        console.print(
            f"[dim]当前权限模式: [bold]{manager.mode}[/]（auto / ask / yolo）[/]"
        )
        return False

    if cmd == "/sessions":
        sessions = Session.list_sessions(sessions_dir=sessions_dir)
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
        session = Session.from_messages(agent.messages, plan=agent.plan)
        path = session.save(sessions_dir=sessions_dir)
        console.print(f"[dim]Session saved: {session.id}[/]")
        return False

    if parts[0].lower() == "/load" and len(parts) > 1:
        session_id = parts[1].strip()
        try:
            session = Session.load(session_id, sessions_dir=sessions_dir)
        except FileNotFoundError as e:
            console.print(f"[bold red]Error:[/] {e}")
            return False
        agent._messages = session.messages
        if session.plan is not None:
            agent.plan.replace(session.plan)
        console.print(
            f"[dim]Loaded session {session.id} "
            f"({len(session.messages)} messages)[/]"
        )
        return False

    console.print(f"[dim]Unknown command: {command} (try /help)[/]")
    return False


if __name__ == "__main__":
    main()
