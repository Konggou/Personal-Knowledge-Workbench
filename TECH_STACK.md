# 个人知识工作台 v1 技术栈与运行策略

## 1. 总体原则

- 前后端分离
- 一个状态库 + 一个向量库
- 前台公开语义统一使用 `project / session / message / knowledge / source`
- `task` 只允许作为内部实现思路，不作为前台主术语
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

### UI 基础库

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

- SSR 主要服务于页面结构稳定和 URL 组织
- 项目页是聊天优先界面，不是控制台
- 不再保留旧的 `/tasks`、`/search`、`/assets`

## 3. 后端

### 主框架

- `Python 3.12`
- `FastAPI 0.135.1`
- `Pydantic 2.12.5`
- `Uvicorn 0.41.0`

### 运行模式

- 单体 API 服务
- 单体进程内托管会话消息生成与资料入库
- 不拆分多服务

### API 语义

- `/projects`
- `/sessions`
- `/knowledge`
- `/sources`

旧 `task` 语义不再作为公开主路线。

## 4. 存储

### 状态库

- `SQLite`

负责：

- 项目
- 项目快照
- 资料元数据
- 会话
- 会话消息
- 消息来源映射

### 向量库

- `Qdrant`

默认使用 embedded 模式，可在本地直接启动，无需额外安装独立服务。

## 5. 检索与模型

### 检索链

- `SQLite FTS`
- `Qdrant semantic recall`
- `hybrid merge`

### 模型能力

- `sentence-transformers 5.2.3` 负责 embedding
- 问答与调研生成由后端统一调度

### 默认策略

- 当前检索链以稳定的混合检索为主
- 后续可继续升级为更强的结构化/语义切块与 rerank

## 6. 实时通信

- SSE 用于会话事件流
- 当前事件流更偏回放式，不是 token 级实时生成

## 7. 测试栈

### 前端

- `Vitest 4.0.18`
- `@testing-library/react 16.3.0`
- `Playwright`

### 后端

- `pytest 9.0.2`

## 8. 启动策略

仓库根目录可直接运行：

- `.\scripts\dev.ps1`
- `.\scripts\start-api.ps1`
- `.\scripts\start-web.ps1`

## 9. 非目标技术项

v1 不做：

- 多租户认证
- 服务拆分
- 旧 schema 兼容迁移
- 插件系统
- 桌面壳分发
