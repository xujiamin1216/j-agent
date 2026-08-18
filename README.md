# j-agent

一个用 Python 实现的 AI Agent，用于实践 **Harness Engineering**——即围绕 LLM 构建脚手架（工具系统、记忆、权限、规划、可观测性等），把原始模型变成一个可用的智能体。

## 功能特性

- **多 Provider 抽象**：支持 Claude / OpenAI，上层逻辑与具体 API 解耦，新增 provider 无需改动核心代码
- **工具系统**：文件读写/编辑、Shell 命令执行、glob 文件匹配、grep 内容搜索，自动发现注册
- **记忆与上下文**：会话持久化（`/save`/`/load`）、上下文窗口截断与压缩、跨会话键值记忆
- **Skills**：用户自定义 prompt 模板，LLM 根据自然语言触发条件自动激活
- **权限系统**：风险分级（safe/confirm/dangerous）、权限模式（auto/ask/yolo）、危险命令检测、交互确认
- **规划与子 Agent**：任务列表拆解跟踪，派生隔离上下文并行执行子任务
- **可观测性**：结构化追踪、`--debug` 调试模式、`--trace` 执行轨迹、按模型价格计算会话成本
- **工作上下文绑定**：绑定工作目录，自动加载 `AGENT.md`，数据按工作目录隔离

## 安装

要求 Python 3.11+。

```bash
# 环境初始化
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## 快速开始

1. 创建配置文件：

```bash
cp .env.example .env
# 编辑 .env，填入 API Key 等信息
```

2. 运行：

```bash
python -m src        # 或安装后直接: j-agent
```

首次启动会打印 Banner、当前 Provider/Model、工具列表等信息，进入交互式 REPL。

### 可选参数

| 参数 | 说明 |
|------|------|
| `--debug` | 实时显示完整的 LLM 请求/响应 |
| `--trace <file>` | 执行轨迹写入 JSONL 文件 |

```bash
python -m src --debug --trace /tmp/j-agent-trace.jsonl
```

## 配置

通过 `.env` 文件或环境变量配置（参见 `.env.example`）：

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|------|--------|------|
| `J_AGENT_PROVIDER` | 否 | `claude` | LLM 提供方（claude/openai） |
| `J_AGENT_API_KEY` | 是 | - | API Key（所有 provider 统一使用） |
| `J_AGENT_BASE_URL` | 否 | provider 默认 | 自定义 API 端点（代理/转发） |
| `J_AGENT_MODEL` | 否 | 按 provider 默认 | 模型标识符 |
| `J_AGENT_SYSTEM_PROMPT` | 否 | 内置默认 | 系统提示词 |
| `J_AGENT_MAX_TOKENS` | 否 | `4096` | 单次响应最大输出 token |
| `J_AGENT_MAX_CONTEXT_TOKENS` | 否 | `100000` | 上下文窗口 token 上限 |
| `J_AGENT_COMPRESS_RATIO` | 否 | `0.6` | 压缩时切割位置比例 |
| `J_AGENT_SUMMARY_RATIO` | 否 | `0.1` | 摘要最大长度占阈值比例 |
| `J_AGENT_PERMISSION_MODE` | 否 | `auto` | 权限模式（auto/ask/yolo） |

## CLI 命令

在 REPL 中输入以下斜杠命令：

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助 |
| `/tools` | 列出已注册的工具 |
| `/skills` | 列出可用的 Skills |
| `/plan` | 查看当前任务计划 |
| `/permission [mode]` | 显示/切换权限模式（auto/ask/yolo） |
| `/sessions` | 列出已保存的会话 |
| `/save` | 保存当前会话 |
| `/load <id>` | 加载已保存的会话 |
| `/exit` | 退出（`/quit`、`/q` 亦可） |

## 工作上下文绑定

Agent 启动时绑定当前工作目录，提供以下能力：

- **AGENT.md**：自动从工作目录加载，内容追加到系统提示词，用于存放工作背景、编码约定、常用命令等
- **.j-agent.env**：工作目录下的配置覆盖全局 `.env`（优先级最高）
- **数据隔离**：记忆与会话持久化到 `<work_dir>/.j-agent/`（`memory.json`、`sessions/`），不同工作目录互不干扰
- **文件沙箱**：文件工具访问被限制在工作目录内，越界（绝对路径或 `..` 穿越）抛错
- **Skills**：在 `.j-agent/skills/<name>/SKILL.md` 定义 Skill prompt 模板

## 测试

```bash
python -m pytest tests/ -v                    # 全部测试
python -m pytest tests/test_tools.py -v       # 单个文件
```

当前共 344 个单元测试，覆盖类型定义、工具系统、记忆、权限、规划、可观测性等模块。

## 架构

代码采用 flat layout，包目录为 `src/`。核心组件：

- `src/agent.py` — 核心 Agent Loop（用户输入 → LLM → 工具调用 → 循环）
- `src/llm/` — LLM Provider 抽象（Claude/OpenAI 适配、统一类型、工厂）
- `src/tools/` — 工具基类、注册表、参数校验、自动发现、内置工具
- `src/memory/` — 会话持久化、Token 计数、上下文管理、跨会话记忆
- `src/skills/` — Skill prompt 模板系统
- `src/permission/` — 权限系统（风险分级、权限模式、危险命令检测）
- `src/planning/` — 任务规划与子 Agent 派生
- `src/observability/` — 结构化追踪、价格表、成本统计
- `src/cli.py` — 交互式 REPL（rich 输出）

详细设计见 [`docs/SDD.md`](docs/SDD.md) 及各阶段文档（`docs/phase-*.md`）。

## 项目结构

```
j-agent/
├── pyproject.toml              # 项目配置 + 依赖
├── .env.example                # 环境变量示例
├── docs/                       # 设计文档（SDD + 各阶段）
├── src/                        # 源码（flat layout）
│   ├── agent.py                # 核心 Agent Loop
│   ├── cli.py                  # CLI REPL
│   ├── config.py               # 配置管理
│   ├── work_context.py         # 工作上下文绑定
│   ├── llm/                    # Provider 抽象层
│   ├── tools/                  # 工具系统
│   ├── memory/                 # 记忆与上下文
│   ├── skills/                 # Skills 系统
│   ├── permission/             # 权限系统
│   ├── planning/               # 规划与子 Agent
│   └── observability/          # 可观测性
└── tests/                      # 单元测试
```

## License

[MIT](LICENSE)
