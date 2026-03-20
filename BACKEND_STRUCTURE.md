# 个人知识工作台 后端结构

## 1. 后端原则

- 前台公开语义统一为：`项目 / 会话 / 消息 / 知识库 / 来源`
- 不再把 `task` 作为前台主模型
- SQLite 是唯一结构化状态中心
- Qdrant 是默认向量检索后端
- 聊天主线是产品事实，后端编排必须服务于项目内对话
- 结果沉淀、来源展示、知识库管理都围绕会话主链展开

## 2. 核心服务

### 2.1 项目服务

职责：

- 创建项目
- 获取项目详情
- 列出项目
- 返回项目级聚合信息

聚合信息包括：

- `active_session_count`
- `active_source_count`
- `latest_session_id`
- `latest_session_title`
- `last_activity_at`

### 2.2 会话服务

职责：

- 创建项目内会话
- 列出项目内会话
- 全局按项目分组列出会话
- 发送消息
- 首条消息后自动生成标题
- 在同一会话内处理普通问答与深度调研
- 生成摘要卡
- 生成报告卡
- 删除结果卡
- 提供会话事件流

### 2.3 来源服务

职责：

- 项目内来源列表
- PDF / DOCX / 网页导入
- 网页刷新
- 网页改链接
- 来源归档 / 恢复 / 删除
- 来源预览
- 入库后同步结构化索引与向量索引
- 可选向当前会话写入 `source_update` 消息

### 2.4 知识库服务

职责：

- 全局资料浏览
- 全局资料搜索
- 按项目分组返回资料

### 2.5 检索服务

职责：

- 词法检索
- 语义检索
- 混合召回
- 项目级证据召回
- grounded 问答复杂度判断
- 条件 rerank
- 低命中时的二次召回

### 2.6 Grounded 生成服务

职责：

- 统一 grounded 主链：`检索 -> 证据选择 -> 证据打包 -> 生成`
- 只保留最终证据集进入回答链路
- 组装 evidence pack 供 LLM 使用
- 优先要求 LLM 返回结构化结果
- 结构化失败时自动降级为 markdown 解析
- 流式生成中断时保留已输出正文并补轻量提示

## 3. 数据存储

### 3.1 SQLite

SQLite 是唯一结构化状态中心，保存：

- 项目
- 会话
- 消息
- 来源
- chunk
- FTS 索引
- 来源挂载关系
- 内部元数据

### 3.2 Qdrant

Qdrant 是默认向量检索层。

默认使用 embedded 模式，方便本地直接运行。

## 4. SQLite Schema

### 4.1 `_app_metadata`

用途：

- 保存 schema version
- 保存 retrieval FTS version

字段：

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`

### 4.2 `projects`

字段：

- `id TEXT PRIMARY KEY`
- `name TEXT NOT NULL`
- `description TEXT NOT NULL`
- `default_external_policy TEXT NOT NULL`
- `status TEXT NOT NULL`
- `current_snapshot_id TEXT NULL`
- `last_activity_at TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `archived_at TEXT NULL`

### 4.3 `project_snapshots`

字段：

- `id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `label TEXT NOT NULL`
- `snapshot_number INTEGER NOT NULL`
- `created_at TEXT NOT NULL`

### 4.4 `sources`

字段：

- `id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `source_type TEXT NOT NULL`
- `title TEXT NOT NULL`
- `canonical_uri TEXT NOT NULL`
- `original_filename TEXT NULL`
- `mime_type TEXT NULL`
- `ingestion_status TEXT NOT NULL`
- `quality_level TEXT NOT NULL`
- `refresh_strategy TEXT NOT NULL`
- `last_refreshed_at TEXT NULL`
- `error_code TEXT NULL`
- `error_message TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `archived_at TEXT NULL`
- `deleted_at TEXT NULL`

### 4.5 `source_chunks`

字段：

- `id TEXT PRIMARY KEY`
- `source_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `snapshot_id TEXT NOT NULL`
- `chunk_index INTEGER NOT NULL`
- `section_label TEXT NOT NULL`
- `section_type TEXT NOT NULL`
- `heading_path TEXT NULL`
- `field_label TEXT NULL`
- `table_origin TEXT NULL`
- `proposition_type TEXT NULL`
- `normalized_text TEXT NOT NULL`
- `excerpt TEXT NOT NULL`
- `char_count INTEGER NOT NULL`
- `retrieval_enabled INTEGER NOT NULL`
- `created_at TEXT NOT NULL`

### 4.6 `source_chunk_fts`

用途：

- SQLite FTS5 在线词法检索索引

### 4.7 `sessions`

字段：

- `id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `title TEXT NOT NULL`
- `title_source TEXT NOT NULL`
- `status TEXT NOT NULL`
- `latest_message_at TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `deleted_at TEXT NULL`

### 4.8 `session_messages`

字段：

- `id TEXT PRIMARY KEY`
- `session_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `seq_no INTEGER NOT NULL`
- `role TEXT NOT NULL`
- `message_type TEXT NOT NULL`
- `title TEXT NULL`
- `content_md TEXT NOT NULL`
- `source_mode TEXT NULL`
- `evidence_status TEXT NULL`
- `disclosure_note TEXT NULL`
- `status_label TEXT NULL`
- `supports_summary INTEGER NOT NULL`
- `supports_report INTEGER NOT NULL`
- `related_message_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `deleted_at TEXT NULL`

### 4.9 `message_sources`

字段：

- `id TEXT PRIMARY KEY`
- `message_id TEXT NOT NULL`
- `session_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `source_kind TEXT NOT NULL`
- `source_id TEXT NULL`
- `chunk_id TEXT NULL`
- `external_uri TEXT NULL`
- `source_rank INTEGER NOT NULL`
- `source_type TEXT NOT NULL`
- `source_title TEXT NOT NULL`
- `canonical_uri TEXT NOT NULL`
- `location_label TEXT NOT NULL`
- `excerpt TEXT NOT NULL`
- `relevance_score REAL NOT NULL`

### 4.10 `memory_entries`

字段：

- `id TEXT PRIMARY KEY`
- `scope_type TEXT NOT NULL`
- `scope_id TEXT NOT NULL`
- `topic TEXT NOT NULL`
- `fact_text TEXT NOT NULL`
- `salience REAL NOT NULL`
- `source_message_id TEXT NULL`
- `created_at TEXT NOT NULL`

## 5. 公开 API

### 项目

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}` (软删除，status 变为 'archived')

### 管理 API

- `POST /api/v1/admin/cleanup` - 手动触发数据清理
- `GET /api/v1/admin/cleanup/preview` - 预览待清理数据

### 会话

- `GET /api/v1/projects/{project_id}/sessions`
- `POST /api/v1/projects/{project_id}/sessions`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages/stream`
- `POST /api/v1/sessions/{session_id}/summary`
- `POST /api/v1/sessions/{session_id}/report`
- `DELETE /api/v1/messages/{message_id}`
- `GET /api/v1/sessions/{session_id}/events`

### 知识库

- `GET /api/v1/knowledge`

### 来源

- `GET /api/v1/projects/{project_id}/sources`
- `POST /api/v1/projects/{project_id}/sources/web`
- `POST /api/v1/projects/{project_id}/sources/files`
- `GET /api/v1/sources/{source_id}`
- `PATCH /api/v1/sources/{source_id}/web`
- `POST /api/v1/sources/{source_id}/refresh`
- `POST /api/v1/sources/{source_id}/archive`
- `POST /api/v1/sources/{source_id}/restore`
- `DELETE /api/v1/sources/{source_id}`

## 6. 删除与归档规则

- **项目删除**：软删除（status 设置为 'archived'），超过 30 天后由清理服务物理删除
- 会话删除：软删除
- 来源删除：软删除
- 结果卡删除：软删除
- 来源归档：退出主检索，但记录保留

## 6.1 数据清理服务 (CleanupService)

自动清理超过 30 天的软删除数据：

- **启动时执行**：API 启动后异步运行，不阻塞服务启动
- **清理范围**：
  - 已归档项目（status='archived' 且 archived_at > 30 天）
  - 项目的所有关联数据（会话、消息、来源、chunks、Qdrant 向量）
- **手动触发**：`POST /api/v1/admin/cleanup`
- **预览**：`GET /api/v1/admin/cleanup/preview`

## 7. 前后端边界

- 前台不得依赖旧 task API
- 前台只消费项目、会话、知识库、来源语义
- 来源气泡只代表最终证据集，不暴露召回候选或内部 rerank 术语
- 来源详细预览可按前端交互使用覆盖式浮层，但不改变后端对象模型

## 8. V2.1 检索基础升级

- grounded 检索在不改变公开 API 的前提下引入两段式策略：
  - 首轮混合检索
  - 次轮上下文改写 / 字段别名扩展 / 条件 HyDE
- 检索会使用最近用户消息作为上下文线索，改善中文追问与代词承接
- 检索诊断仅供后端内部使用，包括：
  - 首轮是否低置信
  - 是否触发上下文改写
  - 是否触发 HyDE
  - 最终来源数
  - 是否形成 grounded candidate

## 9. V2.2 结构化切块

- `source_chunks` 增加结构化检索元数据：
  - `section_type`
  - `heading_path`
  - `field_label`
  - `table_origin`
  - `proposition_type`
- `SourceService` 在入库前构造结构化 chunk：
  - DOCX：保留标题、字段、表格、正文结构
  - PDF：做轻量标题和字段检测
- `SearchService` 将字段块和标题路径视为一等词法信号
- `VectorStore` payload 保留同样的结构化元数据
- 检索支持轻量层级扩展：
  - 标题命中可带出同一 `heading_path` 下的正文
  - 字段命中只在存在范围约束时扩展

## 10. V2.3 Grounded 交付升级

- `GroundedGenerationService` 在检索后增加：
  - 证据选择
  - 上下文压缩
  - evidence pack 组装
- grounded 主链会：
  - 先拉宽内部候选集
  - 用结构感知规则选最终证据预算
  - 压缩长正文为句子级摘录
  - 内部保留 `source_excerpt`
- 低置信的二次召回假阳性会在回答前被拒绝

## 11. V2.4 评测与可观测性

- 增加内部检索评测服务与 CLI：
  - `app.services.retrieval_eval_service`
  - `scripts/run_retrieval_eval.py`
- 本地评测会记录：
  - grounded candidate 状态
  - second-pass 触发状态
  - hit 数
  - packed hit 数
  - retrieval diagnostics
  - grounded-delivery diagnostics
- 这些诊断不暴露到公开 API 或 SSE 合同

## 12. V3 聊天优先 Agent 运行时

### 12.1 运行时主干

- 会话消息流统一走聊天优先的图编排运行时
- 当前默认图编排运行时是唯一主路径
- 不再保留 `v2` 旧链路回退切换
- 不再使用 `WORKBENCH_AGENT_RUNTIME_VERSION` 运行时控制

### 12.2 内部编排

- `AgentOrchestratorService` 是消息轮次的内部图入口
- 图保持边界明确、聊天优先：
  - `chat_graph`
    - `load_turn_context -> load_memory -> classify_turn -> project_retrieval -> optional_web_branch -> evidence_selection -> pre_answer_check`
  - `research_graph`
    - `load_turn_context -> load_memory -> plan_turn -> project_retrieval -> optional_web_branch -> fuse_evidence -> pre_answer_check`
- `pre_answer_check` 支持一次有界的项目侧重试

### 12.3 子系统

- `project_search`
  - 仍由项目内结构化检索栈驱动
- `memory_lookup`
  - 支持会话与项目作用域记忆检索
- `memory_write`
  - 仅在成功回答后写入
- `web_search` / `web_fetch`
  - 仅在用户显式开启 `联网补充` 时启用
- `read_source_context`
  - 供来源预览读取上下文

### 12.4 持久化补充

- 新增表：`memory_entries`
- `message_sources` 支持：
  - `source_kind = project_source | external_web`
  - `source_id` 可空
  - `external_uri` 保存原始网页地址
- grounded 融合保持项目证据优先

## 13. 当前检索与延迟结构

### 13.1 当前检索栈

- grounded 检索当前使用的混合栈：
  - SQLite `FTS5 MATCH`
  - `bm25(...)` 词法排序
  - Qdrant 语义检索
  - `RRF` 融合
  - 融合后有界 rerank
- `source_chunk_fts` 已成为在线检索入口，而不再只是入库时维护的旁路表
- 词法检索在 BM25 之上仍保留结构化加权：
  - `field_label`
  - `heading_path`
  - `section_type`
  - `proposition_type`

### 13.2 融合与 rerank

- 混合融合不再直接相加词法分与语义分
- `SearchService` 使用 `RRF`，因此：
  - 只有词法命中的结果可以保留
  - 只有语义命中的结果可以保留
  - 双路共享命中会自然上浮
- second-pass 结果也并入同一 rank fusion 逻辑
- rerank 层独立为内部服务，支持：
  - `rule`
  - `cross_encoder_local`
  - `cross_encoder_remote`

### 13.3 运行时安全

- retrieval/index version 独立于主 schema version 追踪
- 启动或首次检索时，如果发现：
  - FTS 版本不匹配
  - FTS 行数与最新快照不一致
  - FTS 内容无效
  后端会自动重建 SQLite FTS 索引

### 13.4 评测与诊断

- 内部 retrieval diagnostics 现在区分：
  - `first_pass`
  - `effective_pass`
  - `rerank`
  - fused top score
- `retrieval_eval_service` 会记录：
  - lexical hit 数
  - semantic hit 数
  - fused hit 数
  - rerank backend / applied

### 13.5 默认聊天低延迟路径

- 对普通项目内问答，如果：
  - `deep_research = false`
  - `web_browsing = false`
  则：
  - planner 走启发式
  - pre-answer readiness 走启发式
- 这样保留 grounded 与来源能力的同时，避免默认网页聊天多打两次 LLM
- 只有用户显式开启：
  - `深度调研`
  - `联网补充`
  才进入更重的路径
