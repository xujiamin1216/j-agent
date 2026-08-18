---
title: Phase 6 - 可观测性
version: 0.1.0
date: 2026-08-18
status: 已完成
---

# Phase 6: 可观测性

## 目标

让 Agent 的行为可调试、可追溯：结构化记录 LLM 调用与工具调用、提供实时调试模式、将执行轨迹落盘、并按模型价格计算会话成本。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| 追踪系统 | `observability/tracer.py`: LLM 调用/工具调用的结构化日志 | 已完成 |
| 调试模式 | `--debug` 实时显示完整请求/响应 | 已完成 |
| 执行轨迹 | `--trace <file>` 输出 JSONL 到文件 | 已完成 |
| 成本追踪 | `observability/pricing.py`: 按 model 价格计算，会话结束输出总花费 | 已完成 |

## 模块一览

| 模块 | 路径 | 职责 |
|------|------|------|
| 追踪器 | `observability/tracer.py` | `TraceEvent` / `Tracer`：事件收集、JSONL 输出、聚合统计 |
| 价格表 | `observability/pricing.py` | model → 每 1M token 价格、成本估算 |
| Usage 类型 | `llm/types.py` | `Usage` dataclass + `Message.usage` 字段 |
| Provider 集成 | `llm/claude.py` / `llm/openai_provider.py` | 从 API 响应读取 usage 填充 Message |
| Agent 集成 | `agent.py` | 计时 + 记录 LLM/工具调用 + 发出 `llm_request`/`llm_response` 事件 |
| CLI 集成 | `cli.py` | `--debug`/`--trace` 参数、debug 渲染、会话成本总结 |

## 核心接口

### Usage (`llm/types.py`)

```python
@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    # to_dict() / from_dict()
```

`Message` 新增可选字段 `usage: Usage | None = None`（仅 assistant 消息），`to_dict()`/`from_dict()` 序列化该字段。Provider 从 API 响应提取 usage：

- Claude：`response.usage.input_tokens` / `response.usage.output_tokens`
- OpenAI：`response.usage.prompt_tokens` / `response.usage.completion_tokens`

### Pricing (`observability/pricing.py`)

```python
PRICING: dict[str, tuple[float, float]]   # model 关键词 -> (输入, 输出) USD/1M tokens

def get_pricing(model: str) -> tuple[float, float] | None  # 最长关键词优先匹配
def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float
```

- 关键词匹配不区分大小写，按长度降序匹配（`gpt-4o-mini` 优先于 `gpt-4o`）
- 未知模型返回 `0.0`（不报错）

### Tracer (`observability/tracer.py`)

```python
@dataclass
class TraceEvent:
    timestamp: str
    event: str
    data: dict[str, Any]
    # to_dict()

class Tracer:
    def __init__(self, trace_file: Path | None = None)
    def record_llm_call(self, model, usage, duration_ms) -> None
    def record_tool_call(self, name, arguments, is_error, duration_ms) -> None
    @property
    def events(self) -> list[TraceEvent]
    def summary(self) -> dict[str, Any]   # {llm_calls, tool_calls, input_tokens, output_tokens, total_cost_usd}
```

- 事件记录到内存列表，若设置了 `trace_file` 则同时追加写入 JSONL（每行一个事件）
- `record_llm_call` 累加 token 用量与成本；`summary()` 返回会话级聚合

## Agent 集成

`Agent` 新增可选 `tracer` 参数，在 run 循环中：

1. LLM 调用前后用 `time.perf_counter()` 计时，调用 `tracer.record_llm_call(model, response.usage, duration_ms)`
2. 工具执行前后计时，调用 `tracer.record_tool_call(name, arguments, is_error, duration_ms)`

同时发出两个新事件（供 `--debug` 渲染）：

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `llm_request` | `{model, message_count, tool_names, system, messages}` | LLM 调用前 |
| `llm_response` | `{content, tool_calls, usage}` | LLM 调用后 |

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--debug` | 实时显示完整的 LLM 请求/响应（模型、消息、工具、usage） |
| `--trace <file>` | 执行轨迹写入 JSONL 文件 |

CLI 始终构造 `Tracer`（用于成本追踪），`--trace` 仅决定是否落盘。会话结束时（`/exit` 或 Ctrl-D）若有 LLM 调用，输出「会话统计」面板（调用次数、token 用量、总花费）。

## 设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| usage 传递 | `Message.usage` 可选字段 | 不改 `chat()` 签名，向后兼容，最小侵入 |
| 成本追踪默认开启 | 始终构造 Tracer | 会话结束总花费是核心需求，无需额外开关 |
| trace 落盘 | JSONL 追加写（每行一个事件） | 流式可追加，便于事后逐行分析 |
| 未知模型成本 | 返回 0.0 | 不因价格表缺失而崩溃，自定义模型仍可运行 |
| 调试渲染 | 通过 `on_event` 事件 + `--debug` 标志 | 复用现有事件解耦机制，Agent 不感知 UI |

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_tracer.py` | 14 | 价格查询/成本估算（前缀匹配、未知模型）、Tracer 聚合/事件/JSONL 落盘、TraceEvent 序列化 |
| `tests/test_types.py` (追加) | +4 | `Usage` 序列化往返、`Message.usage` 往返、无 usage 时序列化不含该字段 |

共 344 个单元测试全部通过。

## 验证步骤

```bash
# 1. 验证价格查询
python -c "from src.observability.pricing import get_pricing, estimate_cost; print(get_pricing('claude-sonnet-4-20250514')); print(estimate_cost('claude-sonnet-4-20250514', 1000000, 1000000))"
# 预期: (3.0, 15.0) 和 18.0

# 2. 调试模式（实时显示完整请求/响应）
python -m src --debug

# 3. 执行轨迹落盘
python -m src --trace /tmp/j-agent-trace.jsonl
# 对话几轮后退出，检查 /tmp/j-agent-trace.jsonl 每行一个 JSON 事件

# 4. 成本总结
python -m src
# 对话后 /exit，观察「会话统计」面板输出 token 用量与总花费
```
