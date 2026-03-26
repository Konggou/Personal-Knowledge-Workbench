# Project Identity
本项目是本地运行、聊天优先的个人知识工作台。
- `项目` = 知识库容器
- `会话` = 项目内对话线程
- `消息` = 主要交互单元
- `来源` = 回答底部可展开的轻量证据层
- `知识库` = 资料管理页

# Non-Negotiable
1. 不得做回 task-first 工作台。
2. 不得重新暴露 `/tasks`、`/search`、`/assets` 路由心智。
3. 不得把 `task` 作为前台主术语。
4. 不得擅自扩展到多人协作、认证或 workspace。
5. 必须优先保证主闭环：创建项目 / 新建会话 / 增加资料 / 项目内提问 / 查看来源。
6. 产品好用优先于技术炫技。

# Frontend Terms
- 统一使用：项目 / 会话 / 消息 / 知识库 / 来源 / 深度调研 / 保存为摘要 / 生成报告
- 不要在前台主文案里使用：`task` / `asset` / `task detail`

# Hard Guardrails
- 项目页固定为：顶部轻导航 + 左侧项目树 sidebar + 中间聊天主区。
- 不要常驻右侧知识库栏，不要大型项目头部。
- sidebar 收起后必须缩成窄 rail，并让中间真实变宽。
- 中间消息列与底部输入框必须共用同一中轴。
- 来源气泡先展开标题列表，再进入覆盖式详细预览。
- 摘要卡和报告卡必须留在会话里，不跳独立页面。
- 视觉方向：聊天优先、Academic Editorial 深色主题、暖金强调 `#e6a845`、少卡片少阴影。
- SQLite 是唯一结构化状态中心；Qdrant 是默认向量检索后端。
- 本地 schema 允许直接重建，不做旧数据兼容迁移。
- 删除遵循软删除语义。
- 前台不得依赖旧 task API。
- 普通 grounded 复杂问题只触发 rerank，不自动升级为深度调研。
- 来源气泡只代表最终证据集。
- 内部可保留 task-like orchestration，但前台只能看到：会话 / 消息 / 状态卡 / 结果卡。

# Public Surface
- Routes: `/workspace` `/sessions` `/knowledge` `/settings` `/projects/[projectId]`
- APIs: `/api/v1/projects` `/api/v1/sessions` `/api/v1/knowledge` `/api/v1/sources` `/api/v1/settings`

# Where To Look
- 产品定义、目标、边界： [PRD.md](/Users/user/Desktop/agentic_rag/PRD.md)
- 页面流程、用户路径： [APP_FLOW.md](/Users/user/Desktop/agentic_rag/APP_FLOW.md)
- 前端布局、视觉、交互细则： [FRONTEND_GUIDELINES.md](/Users/user/Desktop/agentic_rag/FRONTEND_GUIDELINES.md)
- 后端结构、服务边界、数据流： [BACKEND_STRUCTURE.md](/Users/user/Desktop/agentic_rag/BACKEND_STRUCTURE.md)
- 技术栈与运行约束： [TECH_STACK.md](/Users/user/Desktop/agentic_rag/TECH_STACK.md)
- 当前实施计划： [IMPLEMENTATION_PLAN.md](/Users/user/Desktop/agentic_rag/IMPLEMENTATION_PLAN.md)
- 最新进展与历史记录： [progress.txt](/Users/user/Desktop/agentic_rag/progress.txt)

# Conflict Resolution
优先级：`PRD.md` > `APP_FLOW.md` > `BACKEND_STRUCTURE.md` / `FRONTEND_GUIDELINES.md` > `TECH_STACK.md` > `IMPLEMENTATION_PLAN.md` > `AGENTS.md`
说明：`AGENTS.md` 只是执行入口，不是产品事实重写层；若冲突，以上层文档为准。
