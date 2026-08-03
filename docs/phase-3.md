---
title: Phase 3 - 记忆与上下文管理
version: 0.1.0
date: 2026-08-03
status: 待开发
---

# Phase 3: 记忆与上下文管理

## 目标

让 Agent 能记住对话、管理有限的上下文窗口。

## 任务

| 任务 | 交付物 |
|------|--------|
| 会话持久化 | `memory/conversation.py`: 保存/加载到 `~/.j-agent/sessions/` |
| Token 计数 | tiktoken (OpenAI), anthropic SDK (Claude) |
| 上下文截断策略 | 保留 system + 最近 N 条，丢弃最早消息 |
| 上下文压缩策略 | 用 LLM 对旧消息生成摘要 |
| 跨会话持久记忆 | `MemoryTool`: Agent 主动保存/读取关键信息 |

## 依赖

| 依赖 | 用途 |
|------|------|
| `tiktoken` | OpenAI token 计数 |
