# 个人知识工作台 技术栈与运行策略

## 1. 总体原则

- 前后端分离
- SQLite 是唯一结构化状态中心
- Qdrant 是默认向量检索后端
- 前台公开语义统一使用：`项目 / 会话 / 消息 / 知识库 / 来源`
- `task` 只允许作为后端内部实现思路，不作为前台主术语
- Windows 优先
- 本地运行优先
- 尽量减少系统级依赖

## 2. 前端

### 主框架

- `Next.js 16.1.6`
- `React 19.2.4`
- `React DOM 19.2.4`
- `TypeScript 5.9.3`

### 核心依赖

- `@tanstack/react-query 5.90.21`
- `zustand 5.0.11`
- `zod 4.3.6`
- `lucide-react 0.577.0`

### UI 基础组件

- `@radix-ui/react-dialog 1.1.15`
- `@radix-ui/react-dropdown-menu 2.1.16`
- `@radix-ui/react-scroll-area 1.2.10`
- `@radix-ui/react-slot 1.2.4`
- `@radix-ui/react-tooltip 1.2.8`

### 页面路由

- `/workspace`
- `/sessions`
- `/knowledge`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=...`

### 约束

- SSR 主要服务于页面结构稳定与 URL 组织
- 项目页是聊天优先界面，不是控制台
- 不再保留旧的 `/tasks`、`/search`、`/assets`

## 3. 后端

### 主框架

- `Python 3.12`
- `FastAPI`
- `Pydantic`
- `Uvicorn`

### 运行模式

- 单体 API 服务
- 单进程内承载会话消息、检索、资料入库和生成逻辑
- 不拆分多服务

### API 语义

- `/api/v1/projects`
- `/api/v1/sessions`
- `/api/v1/knowledge`
- `/api/v1/sources`

旧的 task 语义不再作为公开主路径。

## 4. 存储

### 结构化状态

- `SQLite`

负责保存：

- 项目
- 项目快照
- 资料元数据
- 会话
- 会话消息
- 来源挂载关系
- memory entries
- FTS 元数据

### 向量检索

- `Qdrant`

默认使用 embedded 模式，可在本地直接运行，无需额外安装独立服务。

## 5. 检索与模型

### 检索链

当前主检索链为：

- `SQLite FTS5 MATCH`
- `bm25(...)`
- `Qdrant semantic recall`
- `RRF` 融合
- 有界 rerank

### rerank 能力

- `rule`
- `cross_encoder_local`
- `cross_encoder_remote`

### 模型能力

- `sentence-transformers` 负责 embedding
- LLM 负责：
  - 普通对话
  - grounded 回答生成
  - 深度调研生成

### 默认策略

- 默认网页聊天优先走低延迟路径
- 当本轮消息没有开启：
  - `深度调研`
  - `联网补充`
  planner 与 readiness 优先走启发式

## 6. 实时通信

- SSE 用于会话流式事件
- 当前主要承载：
  - status
  - delta
  - done

## 7. 测试栈

### 前端

- `Vitest`
- `@testing-library/react`
- `Playwright`
- `TypeScript typecheck`

### 后端

- `pytest`
- `compileall`
- 本地 retrieval eval runner

## 8. 数据清理

### CleanupService

自动清理超过 30 天的软删除数据：

- **触发时机**：API 启动时异步执行
- **清理对象**：
  - 已归档项目（status='archived'）
  - 已删除会话（deleted_at 不为空）
  - 已删除来源（deleted_at 不为空）
- **级联清理**：项目删除会级联清理所有关联数据（会话、消息、来源、chunks、Qdrant 向量）
- **手动触发**：`POST /api/v1/admin/cleanup`
- **预览接口**：`GET /api/v1/admin/cleanup/preview`

## 9. 启动策略

仓库根目录可直接运行：

- `.\scripts\dev.ps1`
- `.\scripts\start-api.ps1`
- `.\scripts\start-web.ps1`

默认本地链路：

- Web：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8010`

## 10. 版本演进摘要

### V2

- 上下文改写
- 条件 HyDE
- structured chunking
- evidence selection
- retrieval eval

### 当前运行时能力

- 聊天优先 Agent 运行时
- `联网补充`
- memory entries
- external web evidence

### 当前检索能力

- `FTS5 + bm25`
- `RRF`
- 独立 reranker
- retrieval index version
- 默认聊天低延迟优化

### 当前产品能力

- 软删除 + CleanupService（自动清理过期数据）
- 项目删除功能
- 统一深色主题 UI
- `项目 / 会话 / 消息 / 知识库 / 来源` 完整链路
