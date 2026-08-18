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

配置通过 `.env` 文件进行（参见 `.env.example`）。必填项：`J_AGENT_PROVIDER`（claude/openai）和 `J_AGENT_API_KEY`。可选：`J_AGENT_BASE_URL`（自定义 API 端点）、`J_AGENT_MAX_CONTEXT_TOKENS`（上下文窗口上限，默认 100000）、`J_AGENT_COMPRESS_RATIO`（压缩切割位置比例，默认 0.6）、`J_AGENT_SUMMARY_RATIO`（摘要最大长度占阈值比例，默认 0.1）、`J_AGENT_PERMISSION_MODE`（权限模式 auto/ask/yolo，默认 auto）。工作目录下可放置 `.j-agent.env` 覆盖全局配置（优先级最高）。

**工作上下文绑定**（`src/work_context.py`）：Agent 启动时绑定当前工作目录，提供三项能力：
- **AGENT.md**：自动从工作目录加载 `AGENT.md`，内容追加到系统提示词，用于存放工作背景、编码约定、常用命令等指令。
- **工具工作目录**：`Tool` 基类的 `_resolve_path()` 将相对路径基于工作目录解析，绝对路径不受影响。`ToolRegistry` 在注册时自动设置 `work_dir`。
- **文件工具沙箱**：`Tool._resolve_work_path()` 将 `file_read`/`file_write`/`file_edit` 的访问限制在工作目录内，越界（绝对路径或 `..` 穿越）抛 `PermissionError`；仅在绑定 `work_dir` 时生效（独立使用工具时不受限）。
- **记忆/会话隔离**：`MemoryTool` 和 `Session` 的数据持久化到工作目录下的 `.j-agent/`（如 `.j-agent/memory.json`、`.j-agent/sessions/`），不同工作目录互不干扰。
- **Skills**：用户在工作目录下 `.j-agent/skills/<name>/SKILL.md` 定义 Skill prompt 模板，启动时描述自动注入系统提示词，LLM 根据自然语言触发条件通过 `use_skill` 工具调用。

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

`Agent` 接受 `on_event` 回调，事件类型包括：`tool_call`、`tool_result`、`assistant_response`、`max_iterations`、`context_managed`。CLI（`cli.py`）通过此回调渲染 rich 面板——agent 逻辑不依赖任何 UI。

### 记忆与上下文管理 (`src/memory/`)

- **Token 计数**（`token_counter.py`）：`create_token_counter(provider, model)` 工厂创建计数器。优先使用 AutoTokenizer（中国主流模型 Qwen/GLM/DeepSeek/Baichuan/Yi，需 `pip install -e ".[chinese]"`），OpenAI 用 tiktoken 本地编码（加载失败回退启发式），Claude 用 chars/4 启发式。
- **会话持久化**（`conversation.py`）：`Session` 类保存/加载对话到工作目录下 `.j-agent/sessions/<id>.json`。CLI 支持 `/save`、`/load <id>`、`/sessions` 命令。
- **上下文管理**（`context_manager.py`）：`ContextManager.manage(messages)` 原地修改消息列表。超过阈值时从 `compress_ratio`（默认 60%）位置找安全切割点（user 消息边界），对旧消息用 LLM 生成 `[对话摘要]` 摘要（prompt 限制输出长度）。配置校验确保 `(1-compress_ratio)*1.2 + summary_ratio ≤ 60%`。
- **跨会话记忆**（`memory_store.py` + `tools/builtin/memory.py`）：`MemoryTool` 让 Agent 主动 save/read/list/delete 键值对，持久化到工作目录下 `.j-agent/memory.json`。工具自动发现，无需手动注册。

Agent 接受可选的 `context_manager` 参数，在每次调用 `provider.chat()` 前执行 `manage()`。

### Skills 系统 (`src/skills/`)

Skills 是用户定义的 prompt 模板，LLM 根据自然语言触发条件自动激活。每个 Skill 是 `.j-agent/skills/<name>/` 目录，内含 `SKILL.md`（frontmatter + prompt 正文）及可选脚本和引用文件。

- **渐进式加载**：启动时仅扫描 frontmatter（name、description、script），完整内容按需从磁盘读取。
- **自然语言触发**：Skill 描述注入系统提示词，LLM 判断是否匹配触发条件，通过 `use_skill` 工具调用。
- **脚本支持**：frontmatter `script` 字段指定脚本，调用时执行，stdout 注入 `{{script_output}}`。
- **引用支持**：prompt 中 `@file: path` 指令，展开时内联文件内容（先 skill 目录再工作目录查找）。
- **模板变量**：`{{args}}`（LLM 传入参数）、`{{script_output}}`（脚本输出）。
- **CLI 命令**：`/skills` 列出可用 Skills。

### 权限系统 (`src/permission/`)

防止 Agent 执行危险操作，给用户控制权。

- **风险分级**（`permission/risk.py`）：`RiskLevel` 三级 `safe`/`confirm`/`dangerous`。`Tool` 基类 `risk_level` 类属性默认 `safe`，`bash`/`file_write`/`file_edit`/`use_skill` 标记为 `confirm`。
- **危险操作检测**（`permission/risk.py`）：`detect_dangerous_command()` 用正则匹配 shell 命令（rm、git push/reset/clean、sudo、chmod -R、mkfs、shutdown、fork 炸弹、`curl | sh` 等），`confirm` 工具带 `command` 参数时动态升级为 `dangerous`。
- **权限模式**（`permission/manager.py`）：`PermissionManager` 支持 `auto`（safe 自动放行，confirm/dangerous 确认，默认）/ `ask`（全部确认）/ `yolo`（全部放行）。`check()` 返回 `PermissionDecision`。
- **交互确认**：`PermissionManager` 注入 `ask_callback`，CLI 用 rich 面板展示工具名+参数+风险级别，提示 `[y/N]`；无回调时非 safe 操作默认拒绝（fail-closed）。
- **Agent 集成**：`Agent` 接受可选 `permission_manager`，执行工具前调用 `check()`，拒绝时触发 `permission_denied` 事件并返回 `is_error` 结果（`[权限拒绝] ...`）。
- **CLI 命令**：`/permission` 显示当前模式，`/permission <mode>` 切换；配置项 `J_AGENT_PERMISSION_MODE`。

### 规划与子 Agent (`src/planning/`)

处理复杂的多步骤任务：用任务列表拆解跟踪工作，并用子 Agent 派生隔离的上下文并行执行子任务。

- **计划数据**（`planning/plan.py`）：`Task`（id/title/status/description，status 为 `pending`/`in_progress`/`completed`）与 `Plan`（add_task/get_task/update_task/list_tasks/to_dict/from_dict）。`Plan.replace(other)` 原地替换 tasks 列表，保持对象身份，供会话恢复时 PlanTool 引用仍有效。
- **子 Agent 运行器**（`planning/subagent.py`）：`SubAgentRunner.run(task)` 串行、`run_parallel(tasks)` 用 `ThreadPoolExecutor` 并发；每个子 Agent 拥有独立 `ToolRegistry` 和消息历史（`tools_factory` 构建，排除 `spawn_agent` 防止无界嵌套）。
- **PlanTool**（`tools/builtin/plan.py`）：`action` 支持 `create`/`update`/`list`/`get`，风险级别 `safe`。
- **SpawnAgentTool**（`tools/builtin/spawn.py`）：`task`（单任务）或 `tasks`（并行多任务），风险级别 `confirm`；`runner` 由 CLI 注入。
- **会话持久化**：`Session.plan` 字段保存/加载计划；`/save` 保存 `agent.plan`，`/load` 通过 `agent.plan.replace(session.plan)` 恢复。
- **CLI 命令**：`/plan` 查看当前任务计划。

### 可观测性 (`src/observability/`)

让 Agent 的行为可调试、可追溯：结构化记录 LLM/工具调用、调试模式、执行轨迹落盘、按模型价格计算成本。

- **Usage**（`llm/types.py`）：`Usage`（input_tokens/output_tokens）dataclass，`Message.usage` 可选字段，`to_dict`/`from_dict` 序列化。Claude 从 `response.usage.input/output_tokens` 提取，OpenAI 从 `prompt/completion_tokens` 提取。
- **追踪器**（`observability/tracer.py`）：`Tracer` 记录 `llm_call`（model/usage/耗时/成本）与 `tool_call`（name/参数/是否出错/耗时）事件，聚合 token 用量与成本；构造时传入 `trace_file` 则同时追加写 JSONL。
- **价格表**（`observability/pricing.py`）：`PRICING` 字典按 model 关键词（最长优先、不区分大小写）匹配 `(input, output)` USD/1M tokens；`estimate_cost()` 未知模型返回 0。
- **Agent 集成**（`agent.py`）：`Agent` 接受可选 `tracer`，用 `time.perf_counter()` 计时 LLM 与工具调用并记录；发出 `llm_request`/`llm_response` 事件。
- **CLI 参数**：`--debug` 实时显示完整请求/响应（模型、消息、工具、usage）；`--trace <file>` 轨迹写入 JSONL。Tracer 始终构造，会话结束输出「会话统计」面板（调用次数、token、总花费）。

## 设计文档

总方案 SDD 位于 `docs/SDD.md`，各阶段详细设计拆分为独立文档：

- `docs/SDD.md` -- 总方案（架构、接口、路线图）
- `docs/phase-1.md` -- Phase 1: MVP 核心 Agent Loop（已完成）
- `docs/phase-2.md` -- Phase 2: 工具系统增强（已完成）
- `docs/phase-3.md` -- Phase 3: 记忆与上下文管理（已完成）
- `docs/phase-skills.md` -- Skills: Skill prompt 模板与自然语言触发（已完成）
- `docs/phase-4.md` -- Phase 4: 权限系统（已完成）
- `docs/phase-5.md` -- Phase 5: 规划与子 Agent（已完成）
- `docs/phase-6.md` -- Phase 6: 可观测性（已完成）

## 约定

- Python 3.11+，使用现代类型语法（`list[str]`、`X | None`）
- 所有数据类型使用 dataclass
- 每个模块顶部使用 `from __future__ import annotations`
- 架构变更时需同步更新 SDD 文档
