# Agent Architecture & Core Loop

## 1. 核心定义 (Core Boundaries)
系统在运行过程中，必须严格区分以下四类信息的作用域：
* **Memory (记忆)**：跨会话依然有价值、且无法轻易从当前代码状态重新推导的信息。
* **Task (任务)**：当前工作要做什么、依赖关系如何、进度状态。
* **Plan (计划)**：“当前这一轮”的具体执行步骤安排。
* **System Rules (系统规则/claude.md)**：项目级长期固定的底层运行说明。

## 2. 核心执行闭环 (The Agent Loop)
Agent 的生命周期遵循以下流程，确保记忆的有效读取与沉淀：

1.  **Session Start (会话初始化)**
    * 读取 `claude.md` 获取系统底层行为规范。
    * 读取 `.memory/MEMORY.md` 索引文件，按需加载相关的长期记忆。
2.  **Observation & Planning (观察与计划)**
    * 结合当前用户输入与注入的 Memory 提供方向提示。
    * 核对当前仓库/环境的真实物理状态。如果 Memory 与真实状态冲突，**优先相信当前真实状态**。
    * 生成当前会话的 Task 与局部的 Plan。
3.  **Execution (执行迭代)**
    * 调用工具，修改代码，查阅资源。
    * 在推断具体路径或外部资源前，必须重新验证其有效性。
4.  **Session End / Memory Consolidation (会话结束/记忆固化)**
    * 判断当前会话中是否有“跨会话依旧存在价值”的信息。
    * 调用 `save_memory` 工具，将高价值信息分类落盘。

## 3. 记忆系统架构 (Memory System)
记忆独立落盘，分为以下四种核心类型 (`MEMORY_TYPES`)：

* `user` (Private): 用户的个人偏好（如：缩进风格、回复详略程度）。
* `feedback` (Private/Team): 用户明确纠正过的错误，或验证过的成功经验（正负反馈均需记录）。
* `project` (Team): 不易直接从代码看出的项目约定、架构决策背后的非技术原因（如：合规要求）。
* `reference` (Team): 外部资源指针（如：看板地址、监控面板 URL）。

**禁止存入 Memory 的黑名单**：
文件结构、临时分支名、当前 PR 号、修 Bug 的具体代码细节、密钥凭证。

## 4. 核心工具链 (Tools)

### Tool: `save_memory`
**Description**: 将跨会话依旧重要的信息持久化保存。
**Parameters**:
* `name` (string): 记忆的简短标识名（用于生成文件名）。
* `description` (string): 记忆的核心摘要。
* `type` (enum): 必须是 `user`, `feedback`, `project`, `reference` 之一。
* `content` (string): 具体的记忆内容。
**Behavior**: 
将在 `.memory/` 目录下生成独立的 `{name}.md` 文件（包含 Frontmatter 元数据），并自动同步更新 `.memory/MEMORY.md` 索引文件。
