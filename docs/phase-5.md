---
title: Phase 5 - 规划与子 Agent
version: 0.1.0
date: 2026-08-18
status: 已完成
---

# Phase 5: 规划与子 Agent

## 目标

让 Agent 能处理复杂的多步骤任务：通过任务列表（Plan）拆解与跟踪工作，并通过子 Agent（Sub-Agent）派生隔离的上下文并行执行子任务。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| 任务规划工具 | `PlanTool`: 创建/更新/查看任务列表 | 已完成 |
| 计划持久化 | `Plan` 与会话关联（`Session.plan`），保存/恢复 | 已完成 |
| 子 Agent 派生 | `SpawnAgentTool`: 独立上下文执行子任务 | 已完成 |
| 并行子 Agent | `SubAgentRunner.run_parallel()` 并发执行 | 已完成 |

## 模块一览

| 模块 | 路径 | 职责 |
|------|------|------|
| 计划数据 | `planning/plan.py` | `Task` / `Plan` 数据结构、CRUD、JSON 序列化 |
| 子 Agent 运行器 | `planning/subagent.py` | `SubAgentRunner` 创建隔离 Agent 并运行（串行/并行） |
| 计划工具 | `tools/builtin/plan.py` | `PlanTool`（action: create/update/list/get） |
| 派生工具 | `tools/builtin/spawn.py` | `SpawnAgentTool`（单任务/多任务并行） |
| Agent 集成 | `agent.py` | 持有 `Plan`（供会话持久化） |
| 会话集成 | `memory/conversation.py` | `Session.plan` 字段 + 保存/加载 |
| CLI 集成 | `cli.py` | 注入 plan/runner、`/plan` 命令、会话计划恢复 |

## 核心数据结构

### Task / Plan (`planning/plan.py`)

```python
class TaskStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ALL = (PENDING, IN_PROGRESS, COMPLETED)

@dataclass
class Task:
    id: str
    title: str
    status: str = TaskStatus.PENDING
    description: str = ""
    # to_dict() / from_dict()

@dataclass
class Plan:
    tasks: list[Task]
    def add_task(title, description="") -> Task
    def get_task(task_id) -> Task            # KeyError if missing
    def update_task(task_id, *, status=None, title=None, description=None) -> Task
    def list_tasks() -> list[Task]           # 返回副本
    def replace(other: Plan) -> None         # 原地替换（保持对象身份）
    # to_dict() / from_dict()
```

**`Plan.replace(other)` 的关键设计**：会话加载时通过原地替换 tasks 列表（而非替换 `Plan` 对象本身）来恢复计划，这样 `PlanTool` 持有的 `Plan` 引用始终有效，避免对象身份失效。

### SubAgentRunner (`planning/subagent.py`)

```python
class SubAgentRunner:
    def __init__(self, provider, config, tools_factory=None, permission_manager=None)
    def run(self, task: str) -> str                    # 串行执行单个子任务
    def run_parallel(self, tasks: list[str]) -> list[str]  # ThreadPoolExecutor 并发
    def _make_agent(self) -> Agent                     # 延迟导入，构建隔离 Agent
```

- 每个子 Agent 拥有独立的 `ToolRegistry`（通过 `tools_factory` 构建）和独立消息历史
- `Agent` 采用延迟导入（`TYPE_CHECKING` + 运行时 import），避免循环依赖

## 工具设计

### PlanTool (`tools/builtin/plan.py`)

风险级别：`safe`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | string (required) | `create` / `update` / `list` / `get` |
| `title` | string | 任务标题（create/update） |
| `task_id` | string | 任务 ID（update/get） |
| `status` | string | 任务状态：`pending`/`in_progress`/`completed` |
| `description` | string | 可选任务描述 |

### SpawnAgentTool (`tools/builtin/spawn.py`)

风险级别：`confirm`（派生 Agent 会执行工具，需用户确认）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | string | 单个子任务描述 |
| `tasks` | array<string> | 多个子任务描述（并行执行） |

`runner` 由 CLI 注入；未注入时返回错误提示。

## 计划与会话持久化

`Session` 新增 `plan: Plan | None` 字段：

- `save()` 写入 `"plan": plan.to_dict()`（无计划时为 `null`）
- `load()` 通过 `Plan.from_dict()` 恢复
- `from_messages(messages, plan=None)` 接受计划参数

CLI `/save` 保存 `agent.plan`，`/load` 通过 `agent.plan.replace(session.plan)` 恢复（带 `None` 守卫）。

## 子 Agent 工具隔离

CLI 通过 `_subagent_tools_factory(work_dir)` 为子 Agent 构建工具集，**排除 `spawn_agent`** 防止无界嵌套派生。子 Agent 复用父 Agent 的 `provider`、`config` 与 `permission_manager`。

## 新增 CLI 命令

| 命令 | 功能 |
|------|------|
| `/plan` | 查看当前任务计划 |

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_plan.py` | 15 | Task 默认值/序列化、Plan CRUD、无效状态、序列化往返、`replace` 保持身份 |
| `tests/test_spawn.py` | 7 | SubAgentRunner 串行/并行、工具隔离、SpawnAgentTool 注入/分发 |
| `tests/test_conversation.py` (追加) | +3 | Session 计划保存/加载往返、`from_messages` 携带计划 |

共 326 个单元测试全部通过。

## 验证步骤

```bash
# 1. 验证工具发现（含 plan + spawn_agent）
python -c "from src.tools.discovery import discover_builtin_tools; print(sorted(t.name for t in discover_builtin_tools()))"
# 预期: ['bash', 'file_edit', 'file_read', 'file_write', 'glob', 'grep', 'memory', 'plan', 'spawn_agent', 'use_skill']

# 2. 验证计划数据结构
python -c "from src.planning.plan import Plan; p = Plan(); t = p.add_task('写测试'); print(t.id, p.to_dict())"

# 3. 启动 CLI
python -m src
# 在 REPL 中:
#   让 Agent 用 plan 工具拆解任务，输入 /plan 查看任务列表
#   让 Agent 用 spawn_agent 工具派生子 Agent 并行处理子任务
#   /save 后 /load <id> 验证计划随会话恢复
```
