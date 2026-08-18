---
title: Phase Skills - Skills 系统
version: 0.1.0
date: 2026-08-04
status: 已完成
---

# Phase Skills: Skills 系统

## 目标

让 Agent 能根据用户自然语言输入自动加载专业 prompt 模板（Skills），提供特定领域的指令和上下文。Skills 与工具互补：工具是 LLM 调用的函数，Skills 是 LLM 根据触发条件自动激活的 prompt 模板。

## 任务

| 任务 | 交付物 | 状态 |
|------|--------|------|
| Skill 数据结构 | `skills/skill.py`: `Skill` 数据类 + `SkillRegistry` | 已完成 |
| Skill 自动发现 | `skills/discovery.py`: `discover_skills()` + `build_skill_descriptions()` | 已完成 |
| UseSkillTool | `tools/builtin/skill.py`: LLM 通过工具调用激活 Skill | 已完成 |
| 渐进式加载 | 启动时仅扫描 frontmatter，内容按需读取 | 已完成 |
| 脚本支持 | frontmatter `script` 字段，调用时执行，输出注入 `{{script_output}}` | 已完成 |
| 引用支持 | `@file:path` 指令，展开时内联文件内容 | 已完成 |
| 系统提示注入 | Skill 描述注入 system prompt，LLM 据此判断触发 | 已完成 |
| CLI 命令 | `/skills` 列出可用 Skills | 已完成 |

## 模块一览

| 模块 | 路径 | 职责 |
|------|------|------|
| Skill 核心 | `skills/skill.py` | `Skill` 数据类、`SkillRegistry`、frontmatter 解析、模板展开 |
| Skill 发现 | `skills/discovery.py` | 目录扫描、元数据提取、描述生成 |
| Skill 工具 | `tools/builtin/skill.py` | `UseSkillTool`，LLM 调用以激活 Skill |

## 设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| Skill 目录结构 | `<name>/SKILL.md` | 每个技能自包含，脚本和引用文件可放同一目录 |
| 触发方式 | 自然语言触发（LLM 判断） | 符合标准 Skills 规范，用户无需记忆命令 |
| 触发机制 | 描述注入 system prompt + `use_skill` 工具 | LLM 看到描述后自行判断是否调用 |
| 渐进式加载 | 启动仅读 frontmatter，内容按需读取 | 启动快、内存省、修改实时生效 |
| frontmatter 解析 | 自实现简易解析器 | 不引入 pyyaml 依赖，仅支持 name/description/script |
| 脚本执行 | subprocess + 30s 超时 | 复用 BashTool 模式，防止卡死 |
| 引用路径解析 | 先 skill 目录再 work_dir | 兼顾技能本地文件和项目文件 |
| 模板变量 | `{{args}}`、`{{script_output}}` | 简单直观，无模板引擎依赖 |
| 引用语法 | `@file:path` | 单行指令，正则替换 |

## Skill 目录结构

```
.j-agent/skills/
├── commit/
│   ├── SKILL.md              # Prompt 模板（必需）
│   ├── git-status.sh         # 脚本（可选）
│   └── conventions.md        # 引用文件（可选）
├── review/
│   ├── SKILL.md
│   └── checklist.md
└── echo/
    └── SKILL.md
```

## SKILL.md 文件格式

```markdown
---
name: commit
description: >
  Help create a well-structured git commit. TRIGGER when: user wants to commit
  changes or create a commit. DO NOT TRIGGER when: user asks about git in general.
script: git-status.sh
---
Help the user create a well-structured git commit.

## Current changes
{{script_output}}

## Coding conventions
@file: AGENT.md

## Additional context
{{args}}
```

**Frontmatter 字段**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | Skill 名称（缺省时取目录名） |
| `description` | 是 | 描述 + 触发条件（"TRIGGER when:" / "DO NOT TRIGGER when:"），缺省时取正文首行 |
| `script` | 否 | 脚本文件名（相对于 skill 目录） |

**模板变量**：

| 变量 | 说明 |
|------|------|
| `{{args}}` | LLM 通过工具调用传入的附加参数 |
| `{{script_output}}` | 脚本执行 stdout（无占位符时追加到末尾） |

**引用指令**：

| 指令 | 说明 |
|------|------|
| `@file: path` | 内联文件内容（先 skill 目录再 work_dir 查找） |

## 核心接口

### Skill (`skills/skill.py`)

```python
@dataclass
class Skill:
    name: str                          # Skill 名称
    description: str                   # 描述 + 触发条件
    skill_dir: Path                    # skill 目录路径
    script: str | None = None          # 脚本文件名（可选）

    def load_content(self) -> str      # 按需读取 SKILL.md 内容
    def expand(self, args: str = "") -> str  # 加载并展开全部模板
```

**`expand()` 展开顺序**：
1. 若有 `script`：执行脚本，捕获 stdout
2. 替换 `@file:path` 引用为文件内容
3. 替换 `{{script_output}}` 为脚本输出（无占位符则追加）
4. 替换 `{{args}}` 为参数（无占位符则追加）

### SkillRegistry (`skills/skill.py`)

```python
class SkillRegistry:
    def __init__(self, skills_dir: Path | None = None) -> None
    def register(self, skill: Skill) -> None           # 注册（重名抛 ValueError）
    def get(self, name: str) -> Skill | None            # 按名查找
    def list(self) -> list[Skill]                       # 列出所有（仅元数据）
    def names(self) -> list[str]                        # 列出所有名称
    def invoke(self, name: str, args: str = "") -> str | None  # 调用并展开
    def to_descriptions(self) -> str                    # 生成描述文本（注入 system prompt）
```

### discover_skills (`skills/discovery.py`)

```python
def discover_skills(skills_dir: Path | None = None) -> list[Skill]
    # 扫描子目录，解析 SKILL.md frontmatter，返回 Skill 列表
    # 仅读 frontmatter（渐进式加载），不读正文内容

def build_skill_descriptions(work_dir: Path | None = None) -> str
    # 发现 skills 并生成描述文本，用于 system prompt 注入
```

### UseSkillTool (`tools/builtin/skill.py`)

| 参数 | 类型 | 说明 |
|------|------|------|
| `skill_name` | string (required) | 要调用的 skill 名称 |
| `args` | string | 附加参数或上下文 |

被 `discover_builtin_tools()` 自动发现。`SkillRegistry` 延迟创建（复用 `MemoryTool` 模式），通过 `work_dir` 定位 skills 目录。

## 渐进式加载

```
启动阶段（eager）                     LLM 调用阶段（lazy）
     │                                     │
     ▼                                     ▼
discover_skills()                    UseSkillTool.execute()
+ build_skill_descriptions()              │
     │                                     ▼
     ▼                                 1. 从磁盘读取 SKILL.md 完整内容
扫描 skills/ 子目录                    2. 若有 script：执行脚本
+ 仅读 frontmatter                     3. 替换 @file:path 引用
-> Skill(name, desc, dir, script)     4. 替换 {{script_output}}
+ 描述注入 system prompt              5. 替换 {{args}}
                                      -> 返回展开后的 prompt
```

## 自然语言触发机制

1. **启动时**：`Config.from_env()` 调用 `build_skill_descriptions()` 发现 skills，将描述注入 system prompt
2. **用户输入**：用户用自然语言描述需求（如"帮我提交代码"）
3. **LLM 判断**：LLM 看到 system prompt 中的 skill 描述和触发条件，判断是否匹配
4. **工具调用**：若匹配，LLM 调用 `use_skill(skill_name, args)` 工具
5. **展开返回**：`UseSkillTool` 加载并展开 skill prompt，返回给 LLM
6. **执行指令**：LLM 按 skill 的 prompt 指令执行任务

## 新增 CLI 命令

| 命令 | 功能 |
|------|------|
| `/skills` | 列出所有可用 skills（名称 + 描述首行） |

## 测试

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_skills.py` | 49 | frontmatter 解析、Skill load_content/expand（args/script/引用/组合）、渐进式加载、SkillRegistry CRUD、discover_skills、build_skill_descriptions、UseSkillTool |
| `tests/test_discovery.py` (追加) | +1 | 自动发现包含 use_skill 工具 |

共 239 个单元测试全部通过。

## 验证步骤

```bash
# 1. 验证工具发现（含 use_skill）
python -c "from src.tools.discovery import discover_builtin_tools; print(sorted(t.name for t in discover_builtin_tools()))"
# 预期: ['bash', 'file_edit', 'file_read', 'file_write', 'glob', 'grep', 'memory', 'use_skill']

# 2. 创建测试 skill
mkdir -p .j-agent/skills/echo
cat > .j-agent/skills/echo/SKILL.md << 'EOF'
---
name: echo
description: >
  Echo back what the user says. TRIGGER when: user asks to echo or repeat something.
---
Please echo back: {{args}}
EOF

# 3. 启动 CLI
python -m src
# 在 REPL 中:
#   /skills        -> 应列出 echo skill
#   "帮我echo一下hello" -> LLM 应自动调用 use_skill("echo", "hello")
```
