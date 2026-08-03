# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 构建与运行

```bash
# 环境初始化
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 运行 Agent CLI
python -m src          # 或: j-agent

# 测试
python -m pytest tests/ -v
python -m pytest tests/test_tools.py::TestToolRegistry::test_execute_success -v  # 单个测试
```

配置通过 `.env` 文件进行（参见 `.env.example`）。必填项：`J_AGENT_PROVIDER`（claude/openai）和 `J_AGENT_API_KEY`。可选：`J_AGENT_BASE_URL`（自定义 API 端点，未设置时使用 provider 默认值）。

## 架构

本项目是一个 AI Agent，用于实践 **Harness Engineering**——即围绕 LLM 构建脚手架，将其变为可用的智能体。代码采用 flat layout：包目录为项目根目录下的 `src/`。

### 核心循环 (`src/agent.py`)

`Agent.run(user_input)` 驱动对话流程：追加用户消息 -> 通过 provider 调用 LLM -> 若 LLM 请求工具调用则执行并循环回 -> 返回最终文本响应。设 `MAX_ITERATIONS=20` 上限防止无限循环。

### LLM Provider 抽象层 (`src/llm/`)

`types.py` 中的统一类型（`Message`、`ToolCall`、`ToolResult`、`ToolSpec`）屏蔽了不同 API 的格式差异。`LLMProvider`（base.py）定义接口；`ClaudeProvider`（claude.py）和 `OpenAIProvider`（openai_provider.py）各自负责统一类型与 API 格式的双向转换。`factory.py` 的 `create_provider(config)` 根据 config 创建对应 provider 实例，由 CLI 层调用后注入 Agent。新增 provider 只需实现 `LLMProvider.chat()` 并在 factory 中注册，无需改动 agent 代码。

各 provider 处理的格式差异：Claude 使用 `tool_use` content block 和 user 角色的 `tool_result` 消息；OpenAI 使用 `function` 工具调用和 `role: "tool"` 消息；系统提示在 Claude 中是独立参数，在 OpenAI 中是 system 角色消息。

### 工具系统 (`src/tools/`)

继承 `Tool`，定义 `name`、`description`、`parameters`（JSON Schema），实现 `execute()`。通过 `ToolRegistry` 注册。注册表负责分发、异常捕获（返回 `ToolResult(is_error=True)`）、以及导出 `ToolSpec` 供 LLM 使用。内置工具位于 `tools/builtin/`。

### 事件驱动的 UI 解耦

`Agent` 接受 `on_event` 回调，事件类型包括：`tool_call`、`tool_result`、`assistant_response`、`max_iterations`。CLI（`cli.py`）通过此回调渲染 rich 面板——agent 逻辑不依赖任何 UI。

## 设计文档

总方案 SDD 位于 `docs/SDD.md`，各阶段详细设计拆分为独立文档：

- `docs/SDD.md` -- 总方案（架构、接口、路线图）
- `docs/phase-1.md` -- Phase 1: MVP 核心 Agent Loop（已完成）
- `docs/phase-2.md` -- Phase 2: 工具系统增强（已完成）
- `docs/phase-3.md` ~ `docs/phase-6.md` -- Phase 3-6: 记忆/权限/规划/可观测性（待开发）

## 约定

- Python 3.11+，使用现代类型语法（`list[str]`、`X | None`）
- 所有数据类型使用 dataclass
- 每个模块顶部使用 `from __future__ import annotations`
- 架构变更时需同步更新 SDD 文档
