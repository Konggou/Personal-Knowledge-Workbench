# Personal Knowledge Workbench

一个面向单用户、本地运行、聊天优先的个人知识工作台。

它的核心心智是：

- `项目` 是知识库容器
- `会话` 是项目内对话线程
- `消息` 是主要交互单元
- `来源` 是回答底部可展开的轻量证据层
- `知识库` 负责统一管理网页和文件资料

这不是一个通用聊天壳，也不是多人协作平台。它的目标是让你围绕自己的资料进行问答、调研和结果沉淀。

## 当前状态

当前仓库已经完成 v1 的聊天优先重构，主链可用并带自动化验证：

- 创建项目
- 在项目里新建会话
- 从会话内或知识库页添加网页 / PDF / DOCX
- 在同一会话里提问
- 查看来源气泡并打开来源预览
- 在同一会话里保存摘要卡、生成报告卡

当前项目名称建议统一写作：

- 中文：`个人知识工作台`
- 英文：`Personal Knowledge Workbench`

## 页面结构

公开前端路由：

- `/workspace`
- `/sessions`
- `/knowledge`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=...`

页面职责：

- `工作台`：按项目聚合入口，创建项目并回到最近活跃项目
- `会话`：按项目分组浏览最近会话
- `知识库`：按项目分组管理资料、搜索资料、预览来源、进入聊天
- `项目聊天页`：顶部轻导航、左侧项目树 sidebar、中间主聊天界面

## 主要能力

### 项目与会话

- 新项目创建后直接进入项目空态页
- 项目页不会自动打开最近会话
- 会话标题由首条用户消息自动生成
- 会话支持重命名和删除

### 知识库与资料

支持两类导入路径：

- 在聊天输入区通过 `增加资料`
- 在 `知识库` 页面按项目添加资料

支持三类资料：

- 网页链接
- PDF 文件
- DOCX 文件

支持的资料动作：

- 预览
- 改链接（网页）
- 刷新（网页）
- 归档
- 恢复
- 删除

### 问答与调研

- 默认是项目内问答
- 没有资料时允许进入 `弱资料模式`
- 可切换 `深度调研`，但仍留在同一会话
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
- `Radix UI` 部分基础组件

### 后端

- `Python 3.12`
- `FastAPI 0.135.1`
- `Pydantic 2.12.5`
- `Uvicorn 0.41.0`

### 检索与数据

- `SQLite`：结构化状态中心
- `Qdrant`：向量检索
- `sentence-transformers 5.2.3`：embedding
- `SQLite FTS + Qdrant`：混合检索

默认使用 embedded Qdrant，不需要你先额外安装独立 Qdrant 服务。

## 启动方式

在仓库根目录 `C:\Users\user\Desktop\agentic_rag` 下运行。

### 一键启动

```powershell
.\scripts\dev.ps1
```

### 分开启动

启动 API：

```powershell
.\scripts\start-api.ps1
```

启动 Web：

```powershell
.\scripts\start-web.ps1
```

如果 PowerShell 默认禁止脚本执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

启动后访问：

- Web: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- API Health: [http://127.0.0.1:8010/api/v1/health](http://127.0.0.1:8010/api/v1/health)

## 测试与验证

### 后端

```powershell
apps/api/.venv/Scripts/python.exe -m compileall apps/api/app
apps/api/.venv/Scripts/python.exe -m pytest tests/backend
```

### 前端

```powershell
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

如果你要继续开发，建议按这个顺序读：

1. [AGENTS.md](/Users/user/Desktop/agentic_rag/AGENTS.md)
2. [PRD.md](/Users/user/Desktop/agentic_rag/PRD.md)
3. [APP_FLOW.md](/Users/user/Desktop/agentic_rag/APP_FLOW.md)
4. [TECH_STACK.md](/Users/user/Desktop/agentic_rag/TECH_STACK.md)
5. [FRONTEND_GUIDELINES.md](/Users/user/Desktop/agentic_rag/FRONTEND_GUIDELINES.md)
6. [BACKEND_STRUCTURE.md](/Users/user/Desktop/agentic_rag/BACKEND_STRUCTURE.md)
7. [IMPLEMENTATION_PLAN.md](/Users/user/Desktop/agentic_rag/IMPLEMENTATION_PLAN.md)

## 开发说明

- 这个仓库当前以“聊天优先”作为产品真相
- 不要重新引入旧的 `/tasks`、`/search`、`/assets` 页面心智
- 前台术语应优先使用：`项目 / 会话 / 消息 / 知识库 / 来源`

## V2 方向

后续升级优先聚焦于：

- 更智能的条件 HyDE 触发与中文模糊问法召回
- 更强的 DOCX / PDF 结构化切块与字段提取
- 更稳定的 grounded markdown 输出与列表格式归一化
- 更完善的真实问答评测与端到端回归

## V2 Detailed Direction

The current V2 mainline is intentionally focused on high-yield retrieval and answer-quality work:

- V2.1:
  - query transformation
  - adaptive retrieval
  - contextual follow-up handling
  - conditional HyDE
  - CRAG-lite style retrieval repair
- V2.2:
  - semantic chunking
  - proposition chunking
  - heading / field-aware metadata
  - lightweight hierarchical retrieval
- V2.3:
  - contextual compression before generation
  - relevant segment extraction
  - stronger evidence selection and rerank
- V2.4:
  - evaluation dataset
  - retrieval / generation observability
  - stability-focused end-to-end regression expansion

Not in the current V2 mainline:

- GraphRAG
- Self-RAG
- RL-enhanced RAG
- full multimodal RAG
