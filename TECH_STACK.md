# 技术栈与运行说明

## 1. 目标

本文记录当前稳定技术选型、运行方式、依赖边界与常用开发命令。

产品规则不在本文重复定义，参考 `PRD.md` 与 `AGENTS.md`。

## 2. 前端

- `Next.js 16.1.6`
- `React 19.2.4`
- `TypeScript 5.9.3`
- `pnpm`
- `Vitest` 用于前端测试

前端职责：

- 提供聊天优先 UI
- 管理项目、会话、知识库、来源与设置页
- 消费后端公开 API 与流式事件

## 3. 后端

- `Python 3.12`
- `FastAPI`
- `SQLite`
- `Qdrant`
- `pytest` 用于后端测试

后端职责：

- 提供项目、会话、知识库、来源、设置 API
- 维护 grounded retrieval 与生成链路
- 管理流式消息与证据挂载

## 4. 存储与检索

### 4.1 SQLite

- 唯一结构化状态中心
- 保存项目、会话、消息、来源、FTS、settings 等数据

### 4.2 Qdrant

- 默认向量检索后端
- 本地开发默认 embedded 模式

### 4.3 检索栈

- SQLite FTS5 词法检索
- Qdrant 语义检索
- RRF 融合
- 条件 rerank

## 5. 运行模式

- 默认本地单用户运行
- 不引入多人协作、认证或 workspace 运行假设
- schema 允许本地直接重建，不做旧数据兼容迁移

## 6. 公开路由与 API 家族

### 6.1 前端公开路由

- `/workspace`
- `/sessions`
- `/knowledge`
- `/settings`
- `/projects/[projectId]`

### 6.2 后端公开 API 家族

- `/api/v1/projects`
- `/api/v1/sessions`
- `/api/v1/knowledge`
- `/api/v1/sources`
- `/api/v1/settings`

## 7. 关键能力开关

- `深度调研`：触发研究型回答路径
- `联网补充`：允许在项目证据不足时补入网页证据

这两个开关都属于会话内提问行为，不创建新页面或新对象。

## 8. 常用开发命令

### 8.1 前端

```powershell
corepack pnpm --dir apps/web install
corepack pnpm --dir apps/web dev
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web exec -- vitest run
```

### 8.2 后端

```powershell
cd apps/api
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8010
.venv\Scripts\python.exe -m pytest -q
```

### 8.3 一体联调

- Web 默认：`http://127.0.0.1:3000`
- API 默认：`http://127.0.0.1:8010`
- 健康检查：`/api/v1/health`

## 9. benchmark 与评测

- retrieval benchmark 用于校准默认检索参数
- benchmark 不是前台调参平台
- benchmark 推荐默认值必须与运行时默认值保持一致

当前默认基线：

- `retrieval_mode=hybrid`
- `lexical_candidate_limit=8`
- `semantic_candidate_limit=8`
- `rrf_k=30`
- `reranker_top_n=4`
- `hyde_policy=off`
- `final_retrieval_limit=3`

## 10. 文档边界

- 产品定义：`PRD.md`
- 用户流程：`APP_FLOW.md`
- 前端布局与交互：`FRONTEND_GUIDELINES.md`
- 后端结构与 API：`BACKEND_STRUCTURE.md`
- 当前阶段实施安排：`IMPLEMENTATION_PLAN.md`
- 已完成历史：`progress.txt`
