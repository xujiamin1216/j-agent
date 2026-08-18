---
title: Phase 4 - 权限系统
version: 0.1.0
date: 2026-08-18
status: 已完成
---

# Phase 4: 权限系统

## 目标

防止 Agent 执行危险操作，给用户控制权。在工具执行前，根据工具的风险级别和当前权限模式决定是自动放行、交互确认还是拒绝。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| 工具风险分级 | `safe` / `confirm` / `dangerous` 三级 | 已完成 |
| 权限模式 | `auto` / `ask` / `yolo` 三种模式 | 已完成 |
| 交互确认机制 | 展示工具名 + 参数 + 风险级别，用户选择允许/拒绝 | 已完成 |
| 危险操作检测 | 基于命令模式匹配（rm, git push --force 等） | 已完成 |

## 模块一览

| 模块 | 路径 | 职责 |
|------|------|------|
| 风险分级 | `permission/risk.py` | `RiskLevel` 常量、危险命令模式检测 |
| 权限管理 | `permission/manager.py` | `PermissionMode`、`PermissionDecision`、`PermissionManager` |
| 工具集成 | `tools/base.py` | `Tool.risk_level` 类属性 + `ToolRegistry.risk_levels()` |
| Agent 集成 | `agent.py` | 执行前调用 `PermissionManager.check()`，拒绝时触发 `permission_denied` 事件 |
| 配置 | `config.py` | `permission_mode` 字段 + `J_AGENT_PERMISSION_MODE` 环境变量 |
| CLI 集成 | `cli.py` | 交互确认回调、`/permission` 命令、banner 显示模式 |

## 风险分级

| 级别 | 含义 | 内置工具 |
|------|------|----------|
| `safe` | 只读或受限操作，无需确认 | `file_read`、`glob`、`grep`、`memory` |
| `confirm` | 修改状态或执行代码，需确认 | `file_write`、`file_edit`、`bash`、`use_skill` |
| `dangerous` | 潜在破坏性/不可逆操作 | 由 `bash` 命令模式匹配动态升级 |

**动态升级**：`confirm` 级工具若带有 `command` 参数，且命令匹配危险模式，则升级为 `dangerous`（见下文危险操作检测）。

## 权限模式

| 模式 | 行为 |
|------|------|
| `auto` | `safe` 自动放行；`confirm`/`dangerous` 交互确认（默认） |
| `ask` | 所有工具（含 `safe`）都交互确认 |
| `yolo` | 全部自动放行，不提示 |

## 危险操作检测

`detect_dangerous_command(command)` 用正则模式匹配 shell 命令字符串，命中即视为危险。检测模式覆盖：

| 类别 | 示例模式 |
|------|----------|
| 文件/目录删除 | `rm`、`rmdir` |
| 破坏性 git 操作 | `git push`、`git reset`、`git clean`、`git branch -D`、`git checkout --` |
| 权限提升 | `sudo` |
| 递归改权限 | `chmod -R`、`chown -R` |
| 磁盘/系统操作 | `mkfs`、`dd if=`、`truncate`、`shutdown`、`reboot`、`halt` |
| Fork 炸弹 | `:(){ ... }` |
| 管道注入 shell | `curl ... \| sh`、`... \| sudo` |

## 核心接口

### RiskLevel (`permission/risk.py`)

```python
class RiskLevel:
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"

def detect_dangerous_command(command: str) -> bool      # 命令是否匹配危险模式
def classify_command_risk(command: str) -> str           # 命令 -> CONFIRM / DANGEROUS
```

### PermissionManager (`permission/manager.py`)

```python
@dataclass
class PermissionDecision:
    allowed: bool
    risk_level: str
    reason: str

class PermissionManager:
    def __init__(
        self,
        mode: str = "auto",
        risk_map: dict[str, str] | None = None,          # 工具名 -> 静态风险级别
        ask_callback: AskCallback | None = None,          # (tool_name, arguments, risk) -> bool
    ) -> None

    def check(self, tool_name: str, arguments: dict) -> PermissionDecision
```

**`check()` 决策流程**：

1. 计算有效风险：静态风险级别 + 危险命令动态升级
2. 按模式决策：
   - `yolo` → 全部放行
   - `ask` → 全部走 `ask_callback`
   - `auto` → `safe` 放行，其余走 `ask_callback`
3. 无 `ask_callback` 时非 `safe` 操作默认拒绝（fail-closed）

### Tool 集成 (`tools/base.py`)

```python
class Tool(ABC):
    risk_level: str = RiskLevel.SAFE        # 子类可覆盖

class ToolRegistry:
    def risk_levels(self) -> dict[str, str]  # 工具名 -> 风险级别
```

### Agent 集成 (`agent.py`)

`Agent` 新增可选 `permission_manager` 参数。执行工具前调用 `check()`：

- 拒绝 → 触发 `permission_denied` 事件，返回 `is_error=True` 的 `ToolResult`（`[权限拒绝] ...`），不执行工具
- 放行 → 正常执行

新增事件：

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `permission_denied` | `{name, arguments, risk_level, reason}` | 权限检查拒绝工具调用 |

### 配置 (`config.py`)

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|------|--------|------|
| `J_AGENT_PERMISSION_MODE` | 否 | `auto` | 权限模式（auto/ask/yolo），无效值抛 `RuntimeError` |

## 交互确认

CLI 通过 `_ask_permission(console)` 构造 `ask_callback`：以 rich 面板展示工具名 + 参数（JSON）+ 风险级别（配色：safe 绿 / confirm 黄 / dangerous 红），并提示 `[y/N]` 输入。

## 新增 CLI 命令

| 命令 | 功能 |
|------|------|
| `/permission` | 显示当前权限模式 |
| `/permission <mode>` | 切换权限模式（auto/ask/yolo） |

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_permission.py` | 56 | 危险命令检测、风险分级、PermissionManager 三模式、动态升级、工具风险等级、Agent 拒绝/放行流程、配置解析 |

共 296 个单元测试全部通过。

## 验证步骤

```bash
# 1. 验证工具风险分级
python -c "from src.tools.discovery import discover_builtin_tools; print({t.name: t.risk_level for t in discover_builtin_tools()})"
# 预期: bash/file_write/file_edit/use_skill 为 confirm，其余 safe

# 2. 验证危险命令检测
python -c "from src.permission.risk import detect_dangerous_command; print(detect_dangerous_command('rm -rf /'), detect_dangerous_command('echo hi'))"
# 预期: True False

# 3. 启动 CLI（默认 auto 模式）
python -m src
# 在 REPL 中:
#   /permission        -> 显示当前权限模式 auto
#   /permission yolo   -> 切换为 yolo
#   "帮我删除 /tmp/test.txt" -> bash 危险命令应弹出确认
```
