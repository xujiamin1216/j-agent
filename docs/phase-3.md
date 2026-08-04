---
title: Phase 3 - 记忆与上下文管理
version: 0.1.0
date: 2026-08-03
status: 已完成
---

# Phase 3: 记忆与上下文管理

## 目标

让 Agent 能记住对话、管理有限的上下文窗口。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| 会话持久化 | `memory/conversation.py`: `Session` 类，保存/加载到 `~/.j-agent/sessions/` | 已完成 |
| Token 计数 | `memory/token_counter.py`: AutoTokenizer (中国主流模型), tiktoken (OpenAI), 启发式 chars/4 (Claude) | 已完成 |
| 上下文截断策略 | `memory/context_manager.py`: 保留最近 N 条，丢弃最早消息，不拆散 tool_call 配对 | 已完成 |
| 上下文压缩策略 | `memory/context_manager.py`: 用 LLM 对旧消息生成摘要，替换为 `[对话摘要]` 消息 | 已完成 |
| 跨会话持久记忆 | `tools/builtin/memory.py`: `MemoryTool` (save/read/list/delete) + `memory/memory_store.py` | 已完成 |

## 模块一览

| 模块 | 路径 | 职责 |
|------|------|------|
| Token 计数 | `memory/token_counter.py` | Provider 感知的 token 计数（tiktoken / 启发式） |
| 会话持久化 | `memory/conversation.py` | Session 保存/加载/列表/删除 |
| 上下文管理 | `memory/context_manager.py` | 截断 + 压缩策略 |
| 跨会话记忆 | `memory/memory_store.py` | 键值对持久化存储 |
| 记忆工具 | `tools/builtin/memory.py` | Agent 主动保存/读取记忆 |

## 设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| Claude Token 计数 | 启发式 (chars/4) | 避免 `count_tokens` 服务端 API 调用的延迟和限流 |
| Tiktoken 网络回退 | 编码加载失败时回退到启发式 | tiktoken 需下载 BPE 文件，无网络时降级 |
| 上下文管理 | 原地修改 `_messages` | 避免每次迭代重复压缩；旧消息已被 Session 持久化保留 |
| 安全切割 | 仅在 user 消息边界切割 | 保证 tool 配对完整、对话从 user 开始（Claude API 要求） |
| 比例切割 | 从 60% 位置找切割点 | 适应不同对话长度，替代固定条数 |
| 摘要长度限制 | prompt 中限制输出 ≤ 10% of threshold | 无需递归压缩，LLM 自行决定如何压缩 |
| recent 限制 | ≤ (1-compress_ratio)*1.2 of threshold | 预留空间给摘要，乘 1.2 留余量 |
| 配置校验 | 比例之和 ≤ 60% | 确保压缩后有足够新对话空间 |
| 压缩后截断 | 保留摘要消息，只删最近消息 | 摘要包含旧消息的关键信息，不应被丢弃 |

## 核心接口

### TokenCounter (`memory/token_counter.py`)

```python
class TokenCounter(ABC):
    @abstractmethod
    def count_text(self, text: str) -> int: ...
    def count_messages(self, messages: list[Message]) -> int: ...

class AutoTokenizerCounter(TokenCounter):  # 中国主流模型 (Qwen/GLM/DeepSeek/Baichuan/Yi)
    # HuggingFace AutoTokenizer，需 transformers 包
    # 加载失败回退到启发式
    ...

class TiktokenCounter(TokenCounter):  # OpenAI
    # tiktoken 本地编码，加载失败回退到启发式
    ...

class HeuristicCounter(TokenCounter):  # Claude / fallback
    # max(1, len(text) // 4)
    ...

def create_token_counter(provider: str, model: str) -> TokenCounter: ...
```

**工厂优先级**：AutoTokenizer（中国模型，若可用）> TiktokenCounter（OpenAI）> HeuristicCounter

**支持的中国模型**：Qwen、GLM/ChatGLM、DeepSeek、Baichuan、Yi（通过模型名关键词匹配，映射到 HuggingFace tokenizer 仓库）

### Session (`memory/conversation.py`)

```python
@dataclass
class Session:
    id: str          # UUID
    created_at: str  # ISO 时间戳
    updated_at: str
    messages: list[Message]

    def save(sessions_dir=None) -> Path           # 保存到 ~/.j-agent/sessions/<id>.json
    @classmethod
    def load(cls, session_id, sessions_dir=None) -> Session
    @staticmethod
    def list_sessions(sessions_dir=None) -> list[dict]
    @staticmethod
    def delete(session_id, sessions_dir=None) -> None
    @classmethod
    def from_messages(cls, messages) -> Session
```

### ContextManager (`memory/context_manager.py`)

```python
@dataclass
class ContextManagerConfig:
    max_context_tokens: int = 100_000
    compression_trigger_ratio: float = 0.8
    compress_ratio: float = 0.6       # 从 60% 位置找切割点
    summary_ratio: float = 0.1        # 摘要 ≤ 10% of threshold

class ContextManager:
    def __init__(self, token_counter, provider, config=None): ...  # 含配置校验
    def manage(self, messages: list[Message]) -> dict | None  # 原地修改
```

**管理策略**：
1. 若 token 数 <= threshold (80% of max) -> 无操作
2. 超过阈值 -> 从 `compress_ratio` (60%) 位置找安全切割点，确保 recent ≤ `threshold * (1 - compress_ratio) * 1.2`
3. 对旧消息生成摘要（prompt 限制输出 ≤ `summary_ratio * threshold` tokens）
4. 若摘要 + recent 仍超阈值 -> 后置截断，保留摘要（messages[0]）

**配置校验**：`(1 - compress_ratio) * 1.2 + summary_ratio` ≤ 0.60 正常；0.60~0.70 警告；> 0.70 报错退出。

**安全切割算法**：
- `_is_safe_cut(messages, i)`: `messages[i]` 为 user 角色（保证 tool 配对完整、对话从 user 开始）

### MemoryStore (`memory/memory_store.py`)

```python
class MemoryStore:
    # 存储在 ~/.j-agent/memory.json (dict[str, str])
    def save(self, key: str, value: str) -> str
    def read(self, key: str) -> str       # raises KeyError
    def list_keys(self) -> list[str]
    def delete(self, key: str) -> str      # raises KeyError
```

### MemoryTool (`tools/builtin/memory.py`)

| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | string (required) | `save` / `read` / `list` / `delete` |
| `key` | string | 记忆键 (save/read/delete 必填) |
| `value` | string | 记忆值 (save 必填) |

被 `discover_builtin_tools()` 自动发现。

## 新增环境变量

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|------|--------|------|
| `J_AGENT_MAX_CONTEXT_TOKENS` | 否 | `100000` | 上下文窗口 token 上限 |
| `J_AGENT_COMPRESS_RATIO` | 否 | `0.6` | 压缩时切割位置比例 |
| `J_AGENT_SUMMARY_RATIO` | 否 | `0.1` | 摘要最大长度占阈值比例 |

## 新增 CLI 命令

| 命令 | 功能 |
|------|------|
| `/save` | 保存当前会话 |
| `/load <id>` | 加载已保存的会话 |
| `/sessions` | 列出所有已保存会话 |

## 新增事件

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `context_managed` | `{before_count, after_count}` | 上下文被截断或压缩时 |

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_types.py` (追加) | +7 | `Message.from_dict()` 往返：user/assistant/tool/tool_error |
| `tests/test_token_counter.py` | 35 | 启发式/tiktoken/AutoTokenizer 计数、回退、count_messages、工厂函数、支持模型注册表 |
| `tests/test_conversation.py` | 12 | Session 创建/保存/加载/列表/删除、损坏文件跳过、消息往返 |
| `tests/test_context_manager.py` | 19 | 安全切割检测（user 边界）、比例切割、压缩生成摘要、配置校验、阈值下无操作 |
| `tests/test_memory_store.py` | 11 | CRUD、覆盖写入、持久化跨实例、损坏文件处理 |
| `tests/test_memory_tool.py` | 12 | 四种 action、参数校验、自动发现、spec 有效 |

共 169 个单元测试全部通过（Phase 2 的 73 个 + Phase 3 新增 96 个）。

## 验证步骤

```bash
# 1. 验证工具发现（含 memory）
python -c "from src.tools.discovery import discover_builtin_tools; print(sorted(t.name for t in discover_builtin_tools()))"
# 预期: ['bash', 'file_edit', 'file_read', 'file_write', 'glob', 'grep', 'memory']

# 2. 启动 CLI
python -m src

# 3. 验证会话持久化
# 在 REPL 中对话几轮后输入 /save
# 输入 /sessions 查看已保存会话
# 输入 /load <id> 加载会话

# 4. 验证跨会话记忆
# 在 REPL 中让 Agent 使用 memory 工具保存信息
# 检查 ~/.j-agent/memory.json

# 5. 验证上下文管理
# 长对话后观察 "上下文已管理" 提示
```
