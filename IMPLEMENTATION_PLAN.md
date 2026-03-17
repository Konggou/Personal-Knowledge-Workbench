# 个人知识工作台 v1 实施计划

## 1. 总体目标

交付一个可直接使用、可本地运行、聊天优先的个人知识工作台。

最终必须满足：

- `工作台 / 会话 / 知识库` 导航可用
- 项目聊天页是唯一主工作区
- 资料、来源、问答、深度调研、摘要卡、报告卡都能在同一产品叙事下工作

## 2. 绝对不能断的主闭环

`创建项目 -> 新建会话 -> 增加资料 -> 项目内提问 -> 查看来源`

如果实现压力过大，优先砍外围能力，不破坏这条主链。

## 3. 分阶段计划

### Phase 0 - 规格冻结

目标：

- 冻结聊天优先产品心智

交付物：

- 更新后的 `PRD.md`
- 更新后的 `APP_FLOW.md`
- 更新后的前后端规范文档

明确不做：

- 保留旧的 task / asset 前台叙事

完成定义：

- 全部主文档统一使用 `项目 / 会话 / 消息 / 知识库 / 来源`

### Phase 1 - 数据模型重构

目标：

- 把状态中心从 task / asset 语义切换到 session / message 语义

范围：

- SQLite schema 重构
- schema version 管理
- 本地数据重建机制

交付物：

- `projects`
- `project_snapshots`
- `sources`
- `source_chunks`
- `sessions`
- `session_messages`
- `message_sources`

明确不做：

- 旧数据兼容迁移

完成定义：

- 新 schema 能支撑项目、会话、消息、来源主链

### Phase 2 - 后端 API 重构

目标：

- 用新的公开对象替换旧的 task / search / asset API

范围：

- Projects API
- Sessions API
- Knowledge API
- Sources API

交付物：

- `/api/v1/projects`
- `/api/v1/sessions`
- `/api/v1/knowledge`
- `/api/v1/sources`

明确不做：

- 旧 API 兼容层

完成定义：

- 前端不再依赖旧 task API

### Phase 3 - 聊天优先前端落地

目标：

- 建立新的主工作区

范围：

- 工作台
- 会话页
- 知识库页
- 项目聊天页

交付物：

- 项目空状态
- 聊天输入区
- 会话切换
- 来源气泡
- 摘要卡 / 报告卡

明确不做：

- 独立 task detail
- 独立 asset page

完成定义：

- 用户能在同一会话里完成提问、查看来源、沉淀结果

### Phase 4 - 检索与资料入库稳定化

目标：

- 保证项目内资料可稳定检索

范围：

- 网页 / PDF / DOCX 入库
- 预览
- 刷新
- 归档 / 恢复 / 删除
- 混合检索

完成定义：

- 项目内提问能够稳定命中当前项目资料

### Phase 4.5 - Grounded 生成式 RAG 收口

目标：

- 将 grounded 回答从“命中后直接贴检索文本”升级为真正的生成式 RAG 主链

范围：

- 混合召回后的条件 rerank
- 最终证据选择
- evidence pack 组装
- LLM 结构化优先回答
- markdown 降级
- grounded 与弱资料模式统一流式体验

完成定义：

- 普通 grounded 问答固定只喂 `3` 条最终证据
- 深度调研固定只喂 `5` 条最终证据
- 普通复杂问题只触发 rerank，不自动升级为深度调研
- 来源气泡只展示最终证据，不展示召回候选

### Phase 5 - 项目聊天页整体化重构

目标：

- 将项目页从多卡片工作台改成整体化聊天界面

范围：

- 去掉大型项目头部
- 左侧改为真正的项目树 sidebar
- 中间聊天区成为主视觉
- 去掉常驻右侧知识库栏
- 输入区改为底部一体化聊天输入面

完成定义：

- 聊天区明显大于旧版
- sidebar 收起后主区真实变宽
- 页面不再像多块并排卡片

### Phase 6 - 自动化验证与真实可用性

目标：

- 确保主闭环和核心视觉改动都可回归

范围：

- 后端 pytest
- 前端 vitest
- 前端 build
- Playwright E2E

完成定义：

- 主闭环自动化回归完整可用

## 4. 测试策略

- 后端：`pytest`
- 前端组件：`vitest`
- 前端集成：`next build`
- 前端主链：`playwright`

关键验证项：

- 创建项目
- 新建会话
- 会话内增加资料
- 项目内提问
- 来源气泡展开与预览
- 保存摘要卡
- 生成报告卡
- 从知识库进入聊天

## 5. 可后置项

如果实现压力过大，可优先后置：

- 更强的语义切块
- 更强的 rerank
- 更丰富的来源预览
- 更细粒度的流式输出
- 远程 Qdrant 独立验证

## 6. v1 简化与后续优化

- 普通问答 rerank 最初只按问题长度与关键词触发
- 条件 HyDE 最初是启发式策略，后续再升级
- chunking 初期偏基础，后续再增强语义与结构感知
- evidence selection 初期不强依赖专门模型
- grounded 输出优先结构化，失败时回退 markdown

## 7. 当前阶段判断

当前仓库已经完成到：

- 聊天优先主链可用
- 项目页整体化聊天界面已落地
- 文档已同步到聊天优先产品结构
- 自动化验证覆盖主链
- **V5 项目删除与数据清理功能已落地**
- **Academic Editorial 深色主题已统一**

## 8. V2 路线

高优先级：

- 升级 HyDE 触发逻辑，从简单启发式走向更稳的判定策略
- 强化中文模糊问法、追问、代词承接检索
- 升级 DOCX / PDF 结构化切块与字段抽取
- 提升 grounded 输出稳定性与可读性

中优先级：

- 引入更强的 evidence selection / rerank
- 建立真实问答评测集
- 优化来源层与长回答体验

可延后：

- 继续打磨项目聊天页的视觉层级
- 增补更长链路的 Playwright 覆盖

## 9. V2.1 已落地与映射

### V2.1 已落地

- grounded 检索升级为两段式：
  - 首轮混合检索
  - 次轮上下文改写 / 字段别名扩展 / 条件 HyDE
- 检索会使用最近几轮用户消息作为上下文线索
- 后端新增 `retrieval_diagnostics`
- 保持公开 API 与前台术语不变

### V2 映射

- V2.1：
  - 查询转换
  - 自适应检索
  - 条件 HyDE
  - CRAG-lite
- V2.2：
  - 语义切块
  - 命题切块
  - 标题 / 字段增强
  - 轻量层级检索
- V2.3：
  - 上下文压缩
  - 相关段落提取
  - 更强的 evidence selection / rerank
- V2.4：
  - 最小评测集
  - 检索与生成链路可观测性

### 暂不进入当前 V2 主线

- GraphRAG
- Self-RAG
- RL 增强 RAG
- 完整多模态 RAG

## 10. V3 聊天优先 Agent 运行时升级

- V3 保持公开产品心智不变：
  - 项目
  - 会话
  - 消息
  - 知识库
  - 来源
  - 深度调研
- LangGraph 仅作为内部编排层
- 所有消息发送默认进入有界图运行时
- `联网补充` 是手动按次开启，不是自动升级
- 支持会话记忆与项目记忆
- 外部网页证据与项目资料证据分离管理
- 保留 `WORKBENCH_AGENT_RUNTIME_VERSION=v2` 回退路径

## 11. V4 检索升级方向

- 使用真实的 SQLite `FTS5 + bm25`
- 使用 Qdrant 进行语义召回
- 使用 `RRF` 融合两路结果
- 引入独立 reranker：
  - `rule`
  - `cross_encoder_local`
  - `cross_encoder_remote`
- 增加 retrieval index version 与自动重建
- 增强 retrieval eval 指标
- 默认网页聊天路径优先低延迟：
  - 非 `深度调研`
  - 非 `联网补充`
  的项目内提问尽量避免多余 LLM 调用

## 12. V5 项目生命周期与视觉统一

### 12.1 项目删除功能

- 项目支持软删除（status='archived'）
- 工作台项目卡片右上角 × 按钮删除
- 已归档项目从所有列表中隐藏
- CleanupService 自动清理 30 天前的归档数据
- 清理范围级联：项目 → 会话 → 消息 → 来源 → chunks → Qdrant 向量

### 12.2 视觉主题统一

- 全站统一为 Academic Editorial 深色主题
- 核心配色：
  - Canvas: #0a0c0f
  - Surface: #111419
  - Accent: #e6a845 (金色)
- 字体：DM Serif Display (标题) + Instrument Sans (正文)
- 组件视觉统一：工作台、会话、知识库、项目页
