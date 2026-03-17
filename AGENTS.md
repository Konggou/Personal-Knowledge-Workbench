# Project Identity

这是一个本地运行、聊天优先的个人知识工作台。

产品事实：

- `项目` 是知识库容器
- `会话` 是项目内对话线程
- `消息` 是主要交互单元
- `来源` 是回答底部可展开的轻量证据层
- `知识库` 是资料管理页

# Non-Negotiable Rules

1. 不得把产品重新做回 task-first 工作台。
2. 不得重新暴露旧的 `/tasks`、`/search`、`/assets` 路由心智。
3. 不得把 `task` 作为前台主术语。
4. 不得擅自扩展到多人协作、认证或 workspace。
5. 必须优先保证主闭环：
   - 创建项目
   - 新建会话
   - 增加资料
   - 项目内提问
   - 查看来源
6. 产品好用优先于技术炫技。

# Allowed / Forbidden

## Allowed

- 优化项目聊天页交互
- 优化知识库资料管理
- 优化来源层体验
- 优化检索质量
- 优化摘要卡与报告卡

## Forbidden

- 新增前台 task dashboard
- 新增独立 asset center
- 新增独立 search page
- 把知识库能力藏到用户无法发现
- 把产品叙事改成“Agent 平台”

# Naming Conventions

前台统一使用：

- 项目
- 会话
- 消息
- 知识库
- 来源
- 深度调研
- 保存为摘要
- 生成报告

不要在前台主文案里使用：

- task
- asset
- task detail

# Architecture Summary

## Frontend

- `Next.js 16.1.6`
- `React 19.2.4`
- `TypeScript 5.9.3`

## Backend

- `Python 3.12`
- `FastAPI`
- `SQLite`
- `Qdrant`

## Public Routes

- `/workspace`
- `/sessions`
- `/knowledge`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=...`

## Public API Families

- `/api/v1/projects`
- `/api/v1/sessions`
- `/api/v1/knowledge`
- `/api/v1/sources`

# Design System Summary

核心视觉方向：

- 聊天优先
- 中间聊天区主导
- Academic Editorial 深色主题
- 暖金色强调 (#e6a845)
- 轻分隔线
- 少卡片、少阴影、少并排大面板

项目页结构固定为：

- 顶部轻导航
- 左侧项目树 sidebar
- 中间聊天主区

颜色系统：
- Canvas: #0a0c0f (最深背景)
- Surface: #111419 (卡片背景)
- Text Primary: #f0f0f0
- Text Secondary: #9ca3af
- Accent: #e6a845 (金色强调)

# Frontend Rules

1. 项目页不再允许常驻右侧知识库栏。
2. 项目页不再允许大型项目头部。
3. 左侧 sidebar 展开时显示项目树；收起后必须缩成窄 rail，并让中间真实变宽。
4. 中间消息列与底部输入框必须共用同一中轴。
5. 来源气泡先展开标题列表，再打开覆盖式详细预览。
6. 摘要卡和报告卡必须留在会话里，不跳独立页面。

# Backend Rules

1. SQLite 是唯一结构化状态中心。
2. Qdrant 是默认向量检索后端。
3. 本地 schema 允许直接重建，不做旧数据兼容迁移。
4. 删除遵循软删除语义。
5. 前台不得依赖旧 task API。
6. 普通 grounded 复杂问题只触发 rerank，不自动升级为深度调研；来源气泡只代表最终证据集。

# Task Model Rules

内部可以保留任务式执行思路，但前台只能看到：

- 会话
- 消息
- 状态卡
- 结果卡

如果内部仍有 task-like orchestration，也必须隐藏在后端实现里。

# Source of Truth Documents

- [PRD.md](/Users/user/Desktop/agentic_rag/PRD.md)
- [APP_FLOW.md](/Users/user/Desktop/agentic_rag/APP_FLOW.md)
- [TECH_STACK.md](/Users/user/Desktop/agentic_rag/TECH_STACK.md)
- [FRONTEND_GUIDELINES.md](/Users/user/Desktop/agentic_rag/FRONTEND_GUIDELINES.md)
- [BACKEND_STRUCTURE.md](/Users/user/Desktop/agentic_rag/BACKEND_STRUCTURE.md)
- [IMPLEMENTATION_PLAN.md](/Users/user/Desktop/agentic_rag/IMPLEMENTATION_PLAN.md)
- [progress.txt](/Users/user/Desktop/agentic_rag/progress.txt)

# Conflict Resolution

冲突处理顺序：

1. `PRD.md`
2. `APP_FLOW.md`
3. `BACKEND_STRUCTURE.md` / `FRONTEND_GUIDELINES.md`
4. `TECH_STACK.md`
5. `IMPLEMENTATION_PLAN.md`
6. `AGENTS.md`

说明：

- `AGENTS.md` 是执行入口，不是产品事实重写层。
- 如果 `AGENTS.md` 与下层规范冲突，以下层规范为准。
