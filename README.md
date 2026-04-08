# 个人知识工作台

这是一个面向单用户、本地运行、聊天优先的个人知识工作台。

核心心智是：

- `项目` 是知识容器
- `会话` 是项目内对话线程
- `消息` 是主要交互单元
- `来源` 是回答底部可展开的轻量证据层
- `知识库` 负责统一管理网页和文件资料

它不是通用聊天壳，也不是多人协作平台。它的目标是让你围绕自己的资料完成提问、调研、沉淀和回看。

## 当前状态

当前仓库已经完成聊天优先主链，能够稳定覆盖：

- 创建项目
- 在项目里新建会话
- 从会话内或知识库添加网页 / PDF / DOCX
- 在同一会话里提问
- 查看来源气泡并打开来源预览
- 在会话里保存摘要卡、生成报告卡

## 页面结构

公开前端路由：

- `/workspace`
- `/sessions`
- `/knowledge`
- `/settings`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=...`

页面职责：

- `工作台`：创建项目、浏览最近活跃项目
- `会话`：按项目分组浏览最近会话
- `知识库`：按项目分组管理资料、搜索资料、预览来源
- `设置`：统一配置大模型、向量模型和重排模型
- `项目聊天页`：顶部轻导航、左侧项目树、中央聊天主区

## 主要能力

### 项目与会话

- 新项目创建后直接进入项目页
- 项目页不会自动打开最近会话
- 会话标题由首条用户消息自动生成
- 会话支持重命名和删除

### 知识库与资料

支持两类添加路径：

- 在聊天输入区通过 `增加资料`
- 在 `知识库` 页面按项目添加资料

支持三类资料：

- 网页链接
- PDF 文件
- DOCX 文件

支持的资料动作：

- 预览
- 改链接
- 刷新
- 归档
- 恢复
- 删除

### 问答与调研

- 默认是项目内 grounded 问答
- 没有资料时允许进入弱资料模式继续对话
- 可按次开启 `深度调研`
- 可按次开启 `联网补充`
- 回答底部显示来源气泡

### 结果沉淀

- `保存为摘要` 会在当前会话里追加摘要卡
- `生成报告` 会基于当前会话最近一次有效结论生成报告卡
- 摘要卡和报告卡支持复制与删除

## 技术栈

### 前端

- `Next.js 16.1.6`
- `React 19.2.4`
- `TypeScript 5.9.3`
- `@tanstack/react-query 5.90.21`
- `zustand 5.0.11`

### 后端

- `Python 3.12`
- `FastAPI`
- `Pydantic`
- `Uvicorn`

### 检索与数据

- `SQLite`：结构化状态中心
- `Qdrant`：默认向量检索后端
- `sentence-transformers`：embedding
- `SQLite FTS5 + Qdrant`：混合检索

当前默认使用 embedded Qdrant，不需要额外启动独立服务。

## 启动方式

在仓库根目录下运行，Windows / Linux / macOS 命令一致。

### 首次安装依赖

```sh
corepack pnpm install
```

### 一键启动

```sh
pnpm dev
```

API 和 Web 并发启动，带 `[api]` / `[web]` 彩色前缀输出。

### 启动外部 Qdrant（可选）

默认使用 embedded Qdrant，无需额外操作。如需外部独立服务：

```sh
node scripts/start-qdrant.mjs
```

启动后设置 `WORKBENCH_QDRANT_URL` 指向该服务，再运行 `pnpm dev`。

启动后访问：

- Web: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- API 健康检查: [http://127.0.0.1:8010/api/v1/health](http://127.0.0.1:8010/api/v1/health)

## 测试与验证

### 后端

**Windows：**
```sh
apps/api/.venv/Scripts/python -m compileall apps/api/app
apps/api/.venv/Scripts/python -m pytest tests/backend
apps/api/.venv/Scripts/python scripts/run_retrieval_eval.py --suite all
apps/api/.venv/Scripts/python scripts/run_retrieval_eval.py --suite benchmark --matrix smoke
apps/api/.venv/Scripts/python scripts/run_retrieval_eval.py --suite benchmark --matrix smoke --summary-only
```

**Linux / macOS：**
```sh
apps/api/.venv/bin/python -m compileall apps/api/app
apps/api/.venv/bin/python -m pytest tests/backend
apps/api/.venv/bin/python scripts/run_retrieval_eval.py --suite all
apps/api/.venv/bin/python scripts/run_retrieval_eval.py --suite benchmark --matrix smoke
apps/api/.venv/bin/python scripts/run_retrieval_eval.py --suite benchmark --matrix smoke --summary-only
```

### 前端

```sh
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web test -- --run
corepack pnpm --dir apps/web build
corepack pnpm --dir apps/web test:e2e
```

## 仓库结构

```text
agentic_rag/
├─ apps/
│  ├─ api/                  # FastAPI 后端
│  └─ web/                  # Next.js 前端
├─ scripts/                 # 本地启动脚本
├─ tests/
│  └─ backend/              # 后端回归测试
├─ PRD.md
├─ APP_FLOW.md
├─ TECH_STACK.md
├─ FRONTEND_GUIDELINES.md
├─ BACKEND_STRUCTURE.md
├─ IMPLEMENTATION_PLAN.md
├─ AGENTS.md
└─ progress.txt
```

## 规范文档

建议按下面顺序阅读：

1. [AGENTS.md](/Users/user/Desktop/agentic_rag/AGENTS.md)
2. [PRD.md](/Users/user/Desktop/agentic_rag/PRD.md)
3. [APP_FLOW.md](/Users/user/Desktop/agentic_rag/APP_FLOW.md)
4. [TECH_STACK.md](/Users/user/Desktop/agentic_rag/TECH_STACK.md)
5. [FRONTEND_GUIDELINES.md](/Users/user/Desktop/agentic_rag/FRONTEND_GUIDELINES.md)
6. [BACKEND_STRUCTURE.md](/Users/user/Desktop/agentic_rag/BACKEND_STRUCTURE.md)
7. [IMPLEMENTATION_PLAN.md](/Users/user/Desktop/agentic_rag/IMPLEMENTATION_PLAN.md)

## 开发说明

- 产品真相是“聊天优先”，不要把它重新做回 task-first 工作台
- 不要重新引入旧的 `/tasks`、`/search`、`/assets` 心智
- 前台主术语统一使用：`项目 / 会话 / 消息 / 知识库 / 来源`

## 当前检索说明

当前主检索链路已经升级为：

- SQLite `FTS5 + bm25`
- Qdrant 语义检索
- `RRF` 融合
- 有界 rerank

默认网页聊天场景下，如果本次提问没有开启：

- `深度调研`
- `联网补充`

后端会优先走更轻的启发式 planner / readiness 路径，以降低默认聊天延迟。
## Retrieval Benchmark Defaults

2026-03-20 鐨?full offline retrieval benchmark 宸茬粡鍚屾鍒板綋鍓嶄唬鐮侀粯璁ら厤缃細

- `retrieval_mode=hybrid`
- `lexical_candidate_limit=8`
- `semantic_candidate_limit=8`
- `rrf_k=30`
- `reranker_top_n=4`
- `hyde_policy=off`
- `final_retrieval_limit=3`

濡傛灉鍚庣画 benchmark 鎺ㄨ崘鍊煎彂鐢熷彉鍔紝闇€瑕佸悓姝ユ洿鏂?`apps/api/app/core/settings.py` 鐨勯粯璁ゅ€笺€?
