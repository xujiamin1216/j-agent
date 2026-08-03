---
title: Phase 4 - 权限系统
version: 0.1.0
date: 2026-08-03
status: 待开发
---

# Phase 4: 权限系统

## 目标

防止 Agent 执行危险操作，给用户控制权。

## 任务

| 任务 | 交付物 |
|------|--------|
| 工具风险分级 | `safe` / `confirm` / `dangerous` |
| 权限模式 | `auto` / `ask` / `yolo` |
| 交互确认机制 | 展示工具名+参数+风险级别，用户选择允许/拒绝 |
| 危险操作检测 | 基于命令模式匹配（rm, git push --force 等） |
