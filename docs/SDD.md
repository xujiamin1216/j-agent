---
title: j-agent 软件设计文档 (SDD)
version: 0.1.0
date: 2026-08-03
status: Phase 4 已实现
---

# j-agent 软件设计文档

## 1. 引言

### 1.1 目的

本文档描述 j-agent 的系统架构、模块设计、接口定义及分阶段开发计划。j-agent 是一个用 Python 实现的 AI Agent，目的是实践 **Harness Engineering**--即围绕 LLM 构建脚手架（工具系统、记忆、权限、规划等），将原始模型变成可用的智能体。

### 1.2 范围

j-agent 提供以下核心能力：

- 多 LLM Provider 抽象（Claude / OpenAI），上层逻辑与具体 API 解耦
- 工具注册、校验、分发框架
- 交互式 CLI（REPL）
- 渐进式 Harness 组件：记忆管理、权限系统、任务规划、可观测性

本文档为总方案文档，各阶段详细设计见独立文档（见 [§5 开发计划](#5-开发计划)）。

### 1.3 术语定义

| 术语 | 定义 |
|------|------|
| Harness | 围绕 LLM 构建的脚手架系统，包含工具、记忆、权限等组件 |
| Provider | LLM 供应方接口的抽象实现（Claude、OpenAI 等） |
| Agent Loop | 核心循环：用户输入 -> LLM -> 工具调用 -> 结果回传 -> 输出 |
| ToolSpec | 发送给 LLM 的工具定义（名称、描述、参数 JSON Schema） |
| ToolRegistry | 工具注册表，管理工具的注册、查找和执行分发 |

### 1.4 参考文档

- Anthropic API: https://docs.anthropic.com/en/api
- OpenAI API: https://platform.openai.com/docs/api-reference
- IEEE 1016-2009: Standard for Information Technology-Systems Design Descriptions

---

## 2. 系统概述

### 2.1 设计目标

1. **Provider 无关**：Agent 核心逻辑不依赖特定 LLM API，通过抽象层切换
2. **框架优先**：先建立工具/记忆/权限的框架骨架，再填充具体实现
3. **渐进式**：每个 Phase 产出可独立运行的版本，不依赖后续 Phase
4. **可测试**：核心逻辑通过单元测试覆盖，不依赖真实 API 调用

### 2.2 约束条件

| 约束 | 说明 |
|------|------|
| 语言 | Python 3.11+（使用现代类型语法 `list[str]` 等） |
| 依赖 | anthropic, openai, python-dotenv, rich |
| 运行环境 | 本地终端 CLI |
| API Key | 通过环境变量 / .env 文件提供 |

### 2.3 假设

- 用户已拥有对应 Provider 的有效 API Key
- Phase 2 提供实用工具（文件/shell/搜索）验证 Agent 链路
- 不考虑多用户并发场景（单用户本地交互）

---

## 3. 系统架构

### 3.1 架构分层

```
┌─────────────────────────────────────────────┐
│                  CLI 层 (cli.py)             │
│          交互式 REPL · rich 输出             │
├─────────────────────────────────────────────┤
│              Agent 层 (agent.py)             │
│        核心 Agent Loop · 事件回调             │
├──────────┬──────────┬───────────────────────┤
│  LLM 层  │ Tool 层  │   Harness 组件 (Phase 2-6)  │
│ (llm/)   │ (tools/) │  memory · permission  │
│          │          │  planning · observability   │
├──────────┴──────────┴───────────────────────┤
│              Config 层 (config.py)           │
│        环境变量 · .env · API Key             │
└─────────────────────────────────────────────┘
```

### 3.2 数据流

```
用户输入
  │
  ▼
┌─────────┐     ┌──────────┐     ┌───────────┐
│  Agent  │────▶│  Provider │───▶│  LLM API  │
│  Loop   │◀────│ (Claude/  │◀───│           │
│         │     │  OpenAI)  │    └───────────┘
│         │     └──────────┘
│         │────▶┌──────────┐
│         │     │ToolRegistry│──▶ Tool.execute()
│         │◀────└──────────┘◀─── ToolResult
└─────────┘
  │
  ▼
输出给用户
```

**循环逻辑**：
1. Agent 将用户消息 + 工具定义发送给 Provider
2. Provider 调用 LLM API，返回统一格式的 `Message`
3. 若 `Message` 含 `tool_calls` -> 逐个执行工具 -> 将结果追加到消息历史 -> 回到步骤 2
4. 若 `Message` 为纯文本 -> 返回给用户，等待下一轮输入

### 3.3 模块划分

| 模块 | 路径 | 职责 | Phase |
|------|------|------|-------|
| CLI | `cli.py` | 交互式 REPL、命令处理、rich 输出 | 1 |
| Config | `config.py` | 从环境变量加载配置、创建数据目录 | 1 |
| Agent | `agent.py` | 核心 Agent Loop、事件回调 | 1 |
| LLM Types | `llm/types.py` | Message、ToolCall、ToolResult、ToolSpec | 1 |
| LLM Base | `llm/base.py` | LLMProvider 抽象基类 | 1 |
| LLM Factory | `llm/factory.py` | 根据 Config 创建对应 LLMProvider 实例 | 1 |
| LLM Claude | `llm/claude.py` | Anthropic API 适配 | 1 |
| LLM OpenAI | `llm/openai_provider.py` | OpenAI API 适配 | 1 |
| Tool Base | `tools/base.py` | Tool 基类、ToolRegistry（含校验+截断） | 1 |
| Tool Validation | `tools/validation.py` | JSON Schema 参数校验 | 2 |
| Tool Discovery | `tools/discovery.py` | 自动扫描 builtin/ 注册工具 | 2 |
| File Read Tool | `tools/builtin/file_read.py` | 读取文件内容（带行号） | 2 |
| File Write Tool | `tools/builtin/file_write.py` | 写入/追加文件 | 2 |
| File Edit Tool | `tools/builtin/file_edit.py` | 唯一字符串替换（定向编辑） | 2 |
| Bash Tool | `tools/builtin/bash.py` | Shell 命令执行（带超时） | 2 |
| Glob Tool | `tools/builtin/glob.py` | 文件名 glob 匹配 | 2 |
| Grep Tool | `tools/builtin/grep.py` | 文件内容正则搜索 | 2 |
| Memory | `memory/` | 会话持久化、Token 计数、上下文管理、跨会话记忆 | 3 |
| Skills | `skills/` | Skill prompt 模板、渐进式加载、自然语言触发 | Skills |
| UseSkillTool | `tools/builtin/skill.py` | LLM 调用以激活 Skill | Skills |
| Permission | `permission/` | 风险分级、权限模式、危险操作检测 | 4 |
| Planning | `planning/` | 任务分解、计划跟踪 | 5 |
| Observability | `observability/` | 追踪、日志、成本统计 | 6 |

---

## 4. 详细设计

### 4.1 数据设计

#### 4.1.1 核心数据类型 (`llm/types.py`)

```
┌─────────────────────────────────────────────────────┐
│                    Message                           │
├─────────────────────────────────────────────────────┤
│  role: str            # "user" | "assistant" | "tool"│
│  content: str         # 消息文本内容                  │
│  tool_calls: list[ToolCall]  # LLM 请求的工具调用     │
│  tool_call_id: str | None   # 工具结果对应的调用 ID   │
├─────────────────────────────────────────────────────┤
│  工厂方法:                                           │
│    Message.user(content) -> Message                  │
│    Message.assistant(content, tool_calls) -> Message │
│    Message.tool(tool_call_id, content) -> Message    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────┐  ┌──────────────────────────────────┐
│        ToolCall              │  │           ToolResult              │
├─────────────────────────────┤  ├──────────────────────────────────┤
│  id: str                    │  │  tool_call_id: str               │
│  name: str                  │  │  content: str                    │
│  arguments: dict[str, Any]  │  │  is_error: bool = False          │
└─────────────────────────────┘  └──────────────────────────────────┘

┌─────────────────────────────────────┐
│            ToolSpec                  │
├─────────────────────────────────────┤
│  name: str                          │
│  description: str                   │
│  parameters: dict[str, Any]  # JSON │
│               Schema                │
└─────────────────────────────────────┘
```

#### 4.1.2 配置数据 (`config.py`)

```
┌─────────────────────────────────────────┐
│                Config                    │
├─────────────────────────────────────────┤
│  provider: str        # "claude"|"openai"│
│  model: str           # 模型标识符        │
│  api_key: str         # API 密钥         │
│  system_prompt: str   # 系统提示词        │
│  max_tokens: int      # 最大输出 token   │
│  base_url: str | None # 自定义 API 地址   │
├─────────────────────────────────────────┤
│  工厂方法:                               │
│    Config.from_env() -> Config           │
└─────────────────────────────────────────┘
```

**环境变量映射**：

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|------|--------|------|
| `J_AGENT_PROVIDER` | 否 | `claude` | LLM 提供方 |
| `J_AGENT_API_KEY` | 是 | - | API Key（所有 provider 统一使用） |
| `J_AGENT_BASE_URL` | 否 | provider 默认 | 自定义 API 端点（代理/转发） |
| `J_AGENT_MODEL` | 否 | 按 provider 默认 | 模型标识符 |
| `J_AGENT_SYSTEM_PROMPT` | 否 | 内置默认 | 系统提示词 |
| `J_AGENT_MAX_TOKENS` | 否 | `4096` | 最大输出 token |
| `J_AGENT_MAX_CONTEXT_TOKENS` | 否 | `100000` | 上下文窗口 token 上限 |
| `J_AGENT_KEEP_RECENT_MESSAGES` | 否 | `10` | 截断/压缩时保留的最近消息数 |

**工作上下文绑定**（`src/work_context.py`）：Agent 启动时绑定当前工作目录，提供：
- **AGENT.md**：自动从工作目录加载，内容追加到系统提示词。文件不存在或为空时忽略。
- **工具工作目录**：文件/shell 工具的相对路径基于工作目录解析（`Tool._resolve_path()`），绝对路径不受影响。
- **文件工具沙箱**：文件工具（`file_read`/`file_write`/`file_edit`）通过 `Tool._resolve_work_path()` 将访问限制在工作目录内，越界（绝对路径或 `..` 穿越）抛 `PermissionError`；仅在绑定 `work_dir` 时生效。
- **记忆/会话隔离**：`MemoryTool` 和 `Session` 的数据持久化到 `<work_dir>/.j-agent/`（如 `memory.json`、`sessions/`），不同工作目录互不干扰。
- **配置覆盖**：工作目录下 `.j-agent.env` 覆盖 `.env` 配置（优先级最高）。

### 4.2 接口设计

#### 4.2.1 LLMProvider 接口 (`llm/base.py`)

```python
class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
    ) -> Message:
```

**契约**：
- 输入：对话历史 + 可选工具列表 + 可选系统提示
- 输出：包含文本内容和/或 `tool_calls` 的 `Message`
- 每个 Provider 负责统一格式 ↔ API 格式的双向转换

**Provider 适配对照**：

| 统一概念 | Claude API | OpenAI API |
|----------|------------|------------|
| 工具定义 | `tools[].input_schema` | `tools[].function.parameters` |
| 工具调用 | `content[].tool_use` block | `tool_calls[].function` |
| 工具结果 | `role: "user"` + `tool_result` block | `role: "tool"` + `tool_call_id` |
| 系统提示 | `system` 参数 | `messages[0].role: "system"` |

#### 4.2.2 Tool 接口 (`tools/base.py`)

```python
class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
```

**契约**：
- 子类定义 `name`、`description`、`parameters`（JSON Schema）
- `execute()` 接收已解析的参数，返回字符串结果
- 参数在执行前由 `ToolRegistry` 通过 `validation.py` 校验，失败返回 `ToolResult(is_error=True, content="参数校验失败: ...")`
- 工具输出超过 `MAX_OUTPUT_CHARS`（30000 字符）时自动截断，尾部追加截断提示
- 异常由 `ToolRegistry.execute()` 捕获，转为 `is_error=True` 的 `ToolResult`

#### 4.2.3 ToolRegistry 接口

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None          # 注册工具
    def get(self, name: str) -> Tool | None          # 按名查找
    def execute(self, name: str, arguments: dict) -> ToolResult  # 分发执行
    def to_specs(self) -> list[ToolSpec]             # 导出 LLM 可用的定义
    def names(self) -> list[str]                     # 列出所有名称
```

**异常处理策略**：
- 未知工具名 -> `ToolResult(is_error=True, content="Unknown tool: ...")`
- 工具执行抛异常 -> `ToolResult(is_error=True, content="ErrorType: message")`
- 重复注册 -> `raise ValueError`

#### 4.2.4 Agent 接口 (`agent.py`)

```python
class Agent:
    def __init__(
        self,
        config: Config,
        provider: LLMProvider,
        tools: ToolRegistry | None = None,
        on_event: EventCallback | None = None,
        context_manager: ContextManager | None = None,
    )

    def run(self, user_input: str) -> str
```

Agent 不负责创建 LLMProvider，而是接收外部创建好的实例。Provider 的创建由 `llm/factory.py` 的 `create_provider(config)` 完成，在 CLI 层调用后注入 Agent。

**事件回调** (`on_event`)：

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `tool_call` | `{name, arguments}` | 执行工具前 |
| `tool_result` | `{name, content, is_error}` | 工具执行完成后 |
| `assistant_response` | `{content}` | LLM 返回最终文本 |
| `context_managed` | `{before_count, after_count}` | 上下文被截断或压缩 |
| `max_iterations` | `{message}` | 达到最大迭代次数 |

**安全机制**：
- `MAX_ITERATIONS = 20`：单轮用户输入最多 20 次 LLM 调用，防止无限工具调用循环

### 4.3 组件设计

#### 4.3.1 Agent Loop 详细流程

```
Agent.run(user_input)
│
├─ 1. 添加 Message.user(user_input) 到消息历史
│
├─ 2. 获取工具定义 tool_specs = tools.to_specs()
│
└─ 3. for iteration in range(MAX_ITERATIONS):
       │
       ├─ 3a. 调用 provider.chat(messages, tool_specs, system_prompt)
       │      -> 返回 response: Message
       │
       ├─ 3b. 将 response 追加到消息历史
       │
       ├─ 3c. if response.tool_calls 为空:
       │      -> 触发 assistant_response 事件
       │      -> return response.content  (结束循环)
       │
       └─ 3d. for tc in response.tool_calls:
              ├─ 触发 tool_call 事件
              ├─ result = tools.execute(tc.name, tc.arguments)
              ├─ 触发 tool_result 事件
              └─ 添加 Message.tool(result) 到消息历史
              -> 继续下一轮迭代 (回到 3a)

    4. 若循环耗尽 -> 触发 max_iterations 事件 -> 返回提示信息
```

#### 4.3.2 Provider 创建与适配模式

**创建**：`llm/factory.py` 的 `create_provider(config)` 根据 `config.provider` 实例化对应的 `LLMProvider`，传入 `api_key`、`model`、`max_tokens`、`base_url`。Agent 不负责此逻辑，仅接收已创建的 provider 实例。

**适配**：每个 Provider 实现两个私有转换方法：

- `_to_<provider>_msg(msg: Message) -> dict`：统一消息 -> API 格式
- `_to_<provider>_tool(spec: ToolSpec) -> dict`：统一工具定义 -> API 格式

**Claude 特殊处理**：
- 工具结果消息的 role 为 `"user"`（非 `"tool"`），使用 `tool_result` content block
- assistant 消息含工具调用时，需构建 content blocks 数组

**OpenAI 特殊处理**：
- 系统提示作为 `messages[0]`（role: `"system"`），而非单独参数
- 工具调用参数需 `json.dumps()` 序列化为字符串

---

## 5. 开发计划

### 5.1 分阶段路线图

```
Phase 1 ████████████████████ 完成  MVP: Agent Loop + 工具框架 + 多模型
Phase 2 ████████████████████ 完成  工具系统增强 (文件/shell/grep/校验/自动发现)
Phase 3 ████████████████████ 完成  记忆与上下文管理
Phase 4 ████████████████████ 完成  权限系统
Phase 5 ░░░░░░░░░░░░░░░░░░░░ 待开发  规划与子 Agent
Phase 6 ░░░░░░░░░░░░░░░░░░░░ 待开发  可观测性
```

### 5.2 各阶段文档

| 阶段 | 状态 | 文档 |
|------|------|------|
| Phase 1: MVP - 核心 Agent Loop | 已完成 | [phase-1.md](phase-1.md) |
| Phase 2: 工具系统增强 | 已完成 | [phase-2.md](phase-2.md) |
| Phase 3: 记忆与上下文管理 | 已完成 | [phase-3.md](phase-3.md) |
| Skills: Skill prompt 模板 | 已完成 | [phase-skills.md](phase-skills.md) |
| Phase 4: 权限系统 | 已完成 | [phase-4.md](phase-4.md) |
| Phase 5: 规划与子 Agent | 待开发 | [phase-5.md](phase-5.md) |
| Phase 6: 可观测性 | 待开发 | [phase-6.md](phase-6.md) |

---

## 6. 验证与测试

### 6.1 测试策略

| 层级 | 方法 | 覆盖范围 |
|------|------|----------|
| 单元测试 | pytest | 类型定义、工具框架、工具执行 |
| 集成测试 | 手动 CLI | Agent Loop 端到端（需 API Key） |
| 冒烟测试 | 实用工具 | 验证 LLM -> 工具 -> LLM 链路通畅 |

### 6.2 测试总览

当前共 296 个单元测试，各阶段测试明细见对应阶段文档。

```bash
# 运行全部测试
.venv/bin/python -m pytest tests/ -v
```

---

## 7. 依赖清单

| 依赖 | 版本要求 | 用途 | 引入 Phase |
|------|----------|------|-----------|
| `anthropic` | >=0.40.0 | Claude API SDK | 1 |
| `openai` | >=1.50.0 | OpenAI API SDK | 1 |
| `python-dotenv` | >=1.0.0 | .env 文件加载 | 1 |
| `rich` | >=13.0.0 | 终端彩色输出 | 1 |
| `tiktoken` | >=0.7.0 | OpenAI token 计数 | 3 |
| `transformers` | >=4.40.0 | 中国主流模型 token 计数 (AutoTokenizer) | 3 (optional) |
| `pytest` | >=8.0.0 | 测试框架 | 1 (dev) |
| `pytest-asyncio` | >=0.24.0 | 异步测试支持 | 1 (dev) |

---

## 附录 A: 项目文件结构

```
j-agent/
├── pyproject.toml                  # 项目配置 + 依赖
├── .env.example                    # 环境变量示例
├── .gitignore
├── LICENSE
├── README.md
├── docs/
│   ├── SDD.md                      # 本文档（总方案）
│   ├── phase-1.md                  # Phase 1 详细设计
│   ├── phase-2.md                  # Phase 2 详细设计
│   ├── phase-3.md                  # Phase 3 概要设计
│   ├── phase-4.md                  # Phase 4 概要设计
│   ├── phase-5.md                  # Phase 5 概要设计
│   └── phase-6.md                  # Phase 6 概要设计
├── src/
│   ├── __init__.py
│   ├── __main__.py             # python -m src 入口
│   ├── agent.py                # 核心 Agent Loop
│   ├── cli.py                  # CLI REPL
│   ├── config.py               # 配置管理
│   ├── work_context.py         # 工作上下文绑定
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py             # LLMProvider 抽象基类
│   │   ├── factory.py          # create_provider() 工厂函数
│   │   ├── types.py            # 统一数据类型
│   │   ├── claude.py           # Claude API 适配
│   │   └── openai_provider.py  # OpenAI API 适配
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # Tool 基类 + ToolRegistry（含校验+截断）
│   │   ├── validation.py       # JSON Schema 参数校验
│   │   ├── discovery.py        # 自动发现 builtin/ 工具
│   │   └── builtin/
│   │       ├── __init__.py
│   │       ├── file_read.py    # FileReadTool
│   │       ├── file_write.py   # FileWriteTool
│   │       ├── file_edit.py    # FileEditTool
│   │       ├── bash.py         # BashTool
│   │       ├── glob.py         # GlobTool
│   │       ├── grep.py         # GrepTool
│   │       ├── memory.py       # MemoryTool
│   │       └── skill.py        # UseSkillTool
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── skill.py            # Skill 数据类 + SkillRegistry + frontmatter 解析
│   │   └── discovery.py        # 自动发现 + 描述生成
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── conversation.py        # Session 持久化
│   │   ├── token_counter.py       # Token 计数 (tiktoken / 启发式)
│   │   ├── context_manager.py     # 上下文截断 + 压缩
│   │   └── memory_store.py        # 跨会话键值存储
│   ├── permission/
│   │   ├── __init__.py
│   │   ├── risk.py             # 风险分级 + 危险命令检测
│   │   └── manager.py          # PermissionManager（权限模式 + 决策）
│   ├── planning/               # Phase 5
│   └── observability/          # Phase 6
└── tests/
    ├── __init__.py
    ├── test_types.py
    ├── test_tools.py
    ├── test_validation.py
    ├── test_file_read.py
    ├── test_file_write.py
    ├── test_file_edit.py
    ├── test_bash.py
    ├── test_glob.py
    ├── test_grep.py
    ├── test_discovery.py
    ├── test_token_counter.py
    ├── test_conversation.py
    ├── test_context_manager.py
    ├── test_memory_store.py
    ├── test_memory_tool.py
    ├── test_skills.py
    └── test_permission.py
```
