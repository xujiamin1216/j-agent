---
title: Phase 1 - MVP 核心 Agent Loop
version: 0.1.0
date: 2026-08-03
status: 已完成
---

# Phase 1: MVP - 核心 Agent Loop

## 目标

跑通 "用户输入 -> LLM -> 工具调用 -> 结果回传 -> 输出" 完整循环。

## 任务

| 任务 ID | 任务 | 状态 | 交付物 |
|---------|------|------|--------|
| #6 | 初始化项目结构 | 已完成 | `pyproject.toml`, 目录结构, venv |
| #1 | 实现 LLM 类型定义 | 已完成 | `llm/types.py`: Message, ToolCall, ToolResult, ToolSpec |
| #3 | 实现工具框架 | 已完成 | `tools/base.py`: Tool, ToolRegistry |
| #2 | 实现 LLM Provider 抽象层 | 已完成 | `llm/base.py`, `llm/claude.py`, `llm/openai_provider.py` |
| #4 | 实现配置管理 | 已完成 | `config.py`: Config.from_env() |
| #7 | 实现核心 Agent Loop | 已完成 | `agent.py`: Agent.run() |
| #5 | 实现 CLI 入口 | 已完成 | `cli.py`: REPL + /help /tools /exit |

## 任务依赖关系

```
#6 初始化项目 ──▶ #1 LLM 类型 ──┬──▶ #3 工具框架 ──┐
│                               ├──▶ #2 Provider ──┤
│                               │                   ├──▶ #7 Agent Loop ──▶ #5 CLI
└──▶ #4 配置 ──────────────────┘                   │
```

## 验证结果

16 个单元测试全部通过。
