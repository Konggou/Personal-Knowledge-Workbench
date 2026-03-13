# 个人知识工作台 v1 实施计划

## 1. 总体目标

交付一个可直接使用的、本地运行、聊天优先的知识工作台。

最终必须满足：

- `工作台 / 会话 / 知识库` 导航可用
- 项目聊天页是唯一主工作区
- 资料、来源、问答、调研、摘要卡、报告卡全部在新结构下可用

## 2. 绝对不能断的主链

`创建项目 -> 新建会话 -> 增加资料 -> 项目内提问 -> 查看来源`

如果实现压力过大，优先砍外围功能，不砍这条主链。

## 3. 分阶段计划

### Phase 0 - 规格冻结

目标：

- 冻结聊天优先版产品心智

交付物：

- 更新后的 PRD
- 更新后的 APP_FLOW
- 更新后的前后端规范文档

明确不做：

- 保留 task/asset 旧前台叙事

完成定义：

- 所有文档统一使用 `项目 / 会话 / 消息 / 来源 / 知识库`

### Phase 1 - 数据模型重构

目标：

- 把状态中心从 task/asset 语义切换到 session/message 语义

范围：

- SQLite schema 重构
- schema version 管理
- embedded 数据重建机制

交付物：

- `projects`
- `project_snapshots`
- `sources`
- `source_chunks`
- `sessions`
- `session_messages`
- `message_sources`

明确不做：

- 旧数据迁移兼容

完成定义：

- 新 schema 能支撑项目、会话、消息、来源主链

### Phase 2 - 后端 API 重构

目标：

- 用新公开对象替换旧 task/search/asset API

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

- 项目空态
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

- 保住会话内资料可用性

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

- 将 grounded 回答从“命中后直接铺检索文本”收口为真正的生成式 RAG 主链

范围：

- 混合召回后的条件 rerank
- 最终证据选择
- evidence pack 组装
- LLM 结构化优先回答
- markdown 降级
- grounded 与弱资料统一流式体验

完成定义：

- 普通 grounded 问答固定只喂 `3` 条最终证据
- 深度调研固定只喂 `5` 条最终证据
- 普通复杂问题只触发 rerank，不自动升级深度调研
- 来源气泡只展示最终证据，不展示召回候选

### Phase 5 - 项目聊天页整体化重构

目标：

- 将项目页从多卡片工作台改成整体化聊天界面

范围：

- 删除项目页大型头部
- 左侧改为真正的项目树 sidebar
- 中间聊天区成为主视觉
- 去除常驻右侧知识库栏
- 输入区改成底部悬浮贴边
- 页面改成连续背景 + 轻分隔线

完成定义：

- 聊天区明显大于旧版
- 左侧收起后主区真实变宽
- 页面不再像几块并排卡片

### Phase 6 - 自动化验证与真实可用性

目标：

- 确保主链和核心视觉改动都可回归

范围：

- 后端 pytest
- 前端 vitest
- 前端 build
- Playwright E2E

完成定义：

- 主链自动化回归全绿

## 4. 测试策略

- 后端：`pytest`
- 前端组件：`vitest`
- 前端集成：`next build`
- 前端主链：`playwright`

关键验证项：

- 创建项目
- 新建会话
- 会话内添加资料
- 项目内提问
- 来源气泡展开与预览
- 保存摘要卡
- 生成报告卡
- 从知识库进入聊天

## 5. 可后置项

如果实现压力过大，优先后置：

- 更强的语义切块
- 更强的 rerank
- 更丰富的来源预览
- token 级流式输出
- 独立远程 Qdrant 验证

## 6. v1 简化 / 后续优化

- 普通问答 rerank 仅按问题长度与关键词触发
- 条件 HyDE 目前仅在“首轮检索为空 / 分数偏低 / 关键词覆盖偏弱”时按启发式规则触发，后续可升级为更智能的判定逻辑
- 当前 chunking 仍偏基础，后续可升级为更强的语义/结构化切块
- 当前 evidence selection 仍未引入独立模型 rerank
- 当前 grounded 输出采用“结构化 JSON 优先 + markdown 降级”

## 7. 当前阶段判断

当前仓库已经完成到：

- 聊天优先主链可用
- 项目页整体化聊天界面已落地
- 文档已同步到新布局
- 自动化验证已覆盖主链

## 8. V2 升级路线图

高优先级：

- 升级条件 HyDE 触发逻辑：从当前 v1 启发式规则，逐步过渡到结合真实问句、命中特征和低成本判定器的更智能策略
- 强化中文模糊问法召回：优化代词追问、上下文承接式问题、字段型问法（如题目 / 课题名称 / 项目名称）
- 升级文档切块与字段提取：进一步提升 DOCX / PDF 的标题层级、表格、字段名、章节结构利用率
- 提升 grounded 输出稳定性：继续加强 markdown 列表归一化和 prompt 约束，减少“伪分点挤在一段里”的回答

中优先级：

- 引入更强的 evidence selection / rerank 机制，而不只依赖当前规则法
- 建立真实问答评测集，记录是否命中资料、是否触发 HyDE、最终答案是否可用
- 优化来源层与长回答体验，包括多来源折叠、长文滚动可读性、来源预览衔接

可延后：

- 进一步打磨项目聊天页视觉层级和轻提示样式
- 补更多 Playwright 端到端覆盖，尤其是长对话、复杂 grounded、弱资料连续对话场景

## 9. V2.1 已落地与 V2 映射

### V2.1 已落地

- grounded 检索主链已经升级为两段式策略：
  - 首轮：现有混合检索
  - 次轮：上下文改写 / 字段别名扩展 / 条件 HyDE
- 检索现在会使用最近几轮用户消息作为上下文线索，优先改善中文模糊追问与代词承接问题。
- 后端内部已新增 `retrieval_diagnostics`，至少记录：
  - 首轮是否低命中
  - 是否触发上下文改写
  - 是否触发 HyDE
  - 最终命中来源数
  - 最终是否成为 grounded candidate
- 当前实现保持公开 API 与前台术语不变，不向前端暴露 HyDE、diagnostics、evidence pack 等内部概念。

### 吸收文章后的 V2 映射

- V2.1：
  - 查询转换
  - 自适应检索
  - 条件 HyDE
  - CRAG-lite（仅做检索质量判断与补救）
- V2.2：
  - 语义分块
  - 命题分块
  - 上下文标题增强
  - 轻量分层检索
- V2.3：
  - 上下文压缩
  - 相关段落提取
  - 更强 evidence selection / rerank
- V2.4：
  - 最小评测集
  - 检索与生成链路内部观测
  - 基于评测结果决定是否进入文档增强 RAG 或更强 judge

### 暂不进入当前 V2 主路径

- GraphRAG
- Self-RAG
- RL 增强 RAG
- 完整多模态 RAG
## 10. V2.2 First Slice - Structured Chunking

- Scope completed in this slice:
  - structured chunk metadata added to `source_chunks`
  - DOCX ingestion now preserves heading / paragraph / table-row / field structure
  - PDF ingestion now applies lightweight heading and field detection before chunk assembly
  - retrieval scoring now considers `section_type`, `heading_path`, `field_label`, and `table_origin`
  - source preview now exposes structured chunk metadata for backend/frontend use
- Metadata added for this slice:
  - `section_type`
  - `heading_path`
  - `field_label`
  - `table_origin`
  - `proposition_type` (reserved for later proposition-level work)
- Still deferred inside V2.2:
  - proposition chunk generation
  - richer hierarchical retrieval over chapter summaries
  - stronger PDF layout reconstruction
  - schema-preserving migrations for old local state
