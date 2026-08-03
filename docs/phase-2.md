---
title: Phase 2 - 工具系统增强
version: 0.1.0
date: 2026-08-03
status: 已完成
---

# Phase 2: 工具系统增强

## 目标

从 "能调工具" 到 "有实用的工具可用"。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| 参数 JSON Schema 校验 | `tools/validation.py`: 轻量级校验器（type/required/additionalProperties） | 已完成 |
| 工具执行增强 | `ToolRegistry.execute()` 集成校验 + 输出截断（`MAX_OUTPUT_CHARS=30000`） | 已完成 |
| 实现文件读写工具 | `FileReadTool`（带行号、offset/limit）, `FileWriteTool`（写入/追加、自动建目录）, `FileEditTool`（唯一字符串替换） | 已完成 |
| 实现 shell 执行工具 | `BashTool`（带超时、cwd） | 已完成 |
| 实现代码搜索工具 | `GlobTool`（递归匹配、按时间排序）, `GrepTool`（正则搜索、跳过 .git 等） | 已完成 |
| 工具自动发现 | `tools/discovery.py`: `discover_builtin_tools()` 扫描 `builtin/` 自动注册 | 已完成 |

## 内置工具一览

| 工具 | 参数 | 功能 |
|------|------|------|
| `file_read` | `path`, `offset?`, `limit?` | 读取文件内容（带行号、分页） |
| `file_write` | `path`, `content`, `append?` | 写入/追加文件（自动建目录） |
| `file_edit` | `path`, `old_string`, `new_string` | 唯一字符串替换（定向编辑） |
| `bash` | `command`, `timeout?`, `cwd?` | Shell 命令执行（带超时） |
| `glob` | `pattern`, `path?` | 文件名 glob 匹配（递归） |
| `grep` | `pattern`, `path?`, `include?` | 文件内容正则搜索 |

## 框架增强

- **参数校验**：执行前由 `validation.py` 校验 JSON Schema，失败返回 `ToolResult(is_error=True)`
- **输出截断**：超过 `MAX_OUTPUT_CHARS`（30000 字符）自动截断
- **自动发现**：`discover_builtin_tools()` 扫描 `builtin/` 包，CLI 无需手动注册

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_validation.py` | 11 | JSON Schema 校验：type/required/additionalProperties/boolean |
| `tests/test_file_read.py` | 6 | FileReadTool：正常读取/文件不存在/offset/limit/目录 |
| `tests/test_file_write.py` | 6 | FileWriteTool：写入/追加/自动建目录/Unicode |
| `tests/test_file_edit.py` | 8 | FileEditTool：唯一替换/多行替换/未找到/多次匹配/删除 |
| `tests/test_bash.py` | 6 | BashTool：正常命令/stderr/退出码/超时/cwd |
| `tests/test_glob.py` | 5 | GlobTool：递归匹配/无匹配/排序/截断 |
| `tests/test_grep.py` | 7 | GrepTool：正则/include 过滤/行号/跳过目录 |
| `tests/test_discovery.py` | 4 | 自动发现：全部工具/实例化/无重复/有效 spec |

## 验证步骤

```bash
# 1. 验证工具自动发现
.venv/bin/python -c "from src.tools.discovery import discover_builtin_tools; print(sorted([t.name for t in discover_builtin_tools()]))"
# 预期: ['bash', 'file_edit', 'file_read', 'file_write', 'glob', 'grep']

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 API Key

# 3. 启动 CLI
.venv/bin/python -m src

# 4. 验证工具调用链路
# 在 REPL 中输入: 读取 pyproject.toml 文件
# 预期: Agent 调用 file_read 工具，返回文件内容

# 5. 验证实用工具
# 在 REPL 中输入: 运行 ls -la 命令
# 在 REPL 中输入: 搜索包含 pytest 的文件
```

## 验证结果

73 个单元测试全部通过。
