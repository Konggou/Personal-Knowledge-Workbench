# 个人知识工作台 v1 后端结构

## 1. 后端原则

- 前台公开语义必须是 `project / session / message / knowledge / source`
- 不再把 `task` 作为前台主模型
- 一个状态库 + 一个向量库
- 聊天主线程是表层产品事实
- 会话内结果都通过消息卡表达
- 资料管理与来源预览必须服务于聊天主线

## 2. 核心服务

### 2.1 Project Service

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

### 2.2 Session Service

职责：

- 创建项目内会话
- 列出项目内会话
- 全局按项目分组列出会话
- 发送消息
- 首条消息后自动生成标题
- 在用户显式开启时于同一会话中进入调研
- 生成摘要卡
- 生成报告卡
- 删除结果卡
- 提供会话事件流

### 2.3 Source Service

职责：

- 项目内来源列表
- PDF / DOCX / 网页导入
- 网页刷新
- 网页改链接
- 来源归档 / 恢复 / 删除
- 来源预览
- 入库后同步向量索引
- 可选向当前会话写入 `source_update` 消息

### 2.4 Knowledge Service

职责：

- 全局资料浏览
- 全局资料搜索
- 按项目分组返回资料

### 2.5 Search Service

职责：

- lexical retrieval
- semantic retrieval
- hybrid merge
- 项目级证据召回
- 普通 grounded 问答复杂度判定
- 普通 grounded 条件 rerank
- 低命中时的条件 HyDE / 查询扩展二次召回

说明：

- 当前条件 HyDE 触发仍是 v1 启发式规则：首轮无结果、首条分数偏低、或关键词覆盖偏弱时才触发
- 后续可升级为更智能的触发逻辑，例如结合真实问句日志、更多检索特征，或引入轻量判定模型

### 2.6 Grounded Generation Service

职责：

- 将 grounded 问答统一为 `检索 -> 证据选择 -> 证据包 -> 生成`
- 只保留最终证据集进入回答链
- 组装 evidence pack 供 LLM 使用
- 优先要求 LLM 返回结构化 JSON
- JSON 非法时自动降级为 markdown 解析
- 流式生成中途失败时保留已输出正文并补轻尾注

## 3. 数据存储

### 3.1 SQLite

SQLite 是唯一结构化状态中心。

### 3.2 Qdrant

Qdrant 是默认向量索引层。

默认使用 embedded 模式。

## 4. SQLite Schema

### 4.1 `_app_metadata`

用途：

- 存 schema version

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
- `chunk_index INTEGER NOT NULL`
- `location_label TEXT NOT NULL`
- `normalized_text TEXT NOT NULL`
- `char_count INTEGER NOT NULL`
- `created_at TEXT NOT NULL`

### 4.6 `source_chunk_fts`

用途：

- SQLite FTS 检索

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
- `source_id TEXT NOT NULL`
- `chunk_id TEXT NULL`
- `source_rank INTEGER NOT NULL`
- `source_type TEXT NOT NULL`
- `source_title TEXT NOT NULL`
- `canonical_uri TEXT NOT NULL`
- `location_label TEXT NOT NULL`
- `excerpt TEXT NOT NULL`
- `relevance_score REAL NOT NULL`

## 5. 公开 API

### Projects

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`

### Sessions

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

### Knowledge

- `GET /api/v1/knowledge`

### Sources

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

- 会话删除：软删除
- 来源删除：软删除
- 结果卡删除：软删除
- 来源归档：退出主检索，但记录保留

## 7. 前后端边界

- 前端不依赖旧 task API
- 前端只消费项目、会话、知识库、来源语义
- 来源气泡只代表最终喂给模型的证据，不暴露召回候选或内部 rerank 术语
- 来源详细预览可按前端交互使用覆盖式浮层，但不改变后端对象模型

## 8. V2.1 Retrieval Foundation

- The grounded retrieval path now keeps the public API unchanged while adding an internal two-stage strategy:
  - first pass hybrid retrieval
  - second pass contextual rewrite / field alias expansion / conditional HyDE
- Retrieval now accepts recent user-message history as context clues for follow-up questions.
- Internal retrieval diagnostics are recorded for backend use only:
  - whether first pass was low confidence
  - whether contextual rewrite was triggered
  - whether HyDE was triggered
  - final source count
  - final grounded candidate status
- Diagnostics are intentionally not exposed in frontend payloads or SSE semantics.

## 9. V2 Direction After Article Review

- Near-term priorities:
  - query transformation
  - adaptive retrieval
  - CRAG-lite style retrieval repair
  - semantic / proposition chunking
  - lightweight hierarchical retrieval
  - contextual compression and relevant-segment extraction
- Explicitly out of the current V2 mainline:
  - GraphRAG
  - Self-RAG
  - RL-enhanced RAG
  - full multimodal RAG
## 10. V2.2 Structured Chunking Notes

- `source_chunks` now carries structured retrieval metadata:
  - `section_type`
  - `heading_path`
  - `field_label`
  - `table_origin`
  - `proposition_type`
- `SourceService` now builds structured chunk blocks before persistence:
  - DOCX: heading-aware, field-aware, table-aware
  - PDF: lightweight heading/field detection plus body chunk assembly
- Proposition chunks are now generated from structured body/field content and classified into lightweight proposition types.
- `SearchService` now treats field chunks and heading paths as first-class lexical signals.
- `VectorStore` payloads now persist the same metadata so semantic hits can be merged back with structured context.
- `SearchService` now also performs a lightweight hierarchical expansion step:
  - anchor hits from headings can pull in sibling body chunks under the same `heading_path`
  - field hits only expand when they already belong to a scoped heading path
  - this is intentionally a light retrieval repair layer, not a full chapter-summary hierarchy

## 11. V2.3 Grounded Delivery Notes

- `GroundedGenerationService` now inserts an internal `selection -> compression -> evidence pack` layer after retrieval.
- Grounded delivery now:
  - requests a wider internal candidate set
  - selects the final evidence budget with a structure-aware selector
  - compresses long body evidence into sentence-focused excerpts
  - preserves `source_excerpt` separately for internal prompt/debug use
- Delivery diagnostics now include:
  - `selection`
  - `compression`
  - `selected_evidence_count`
- Low-confidence second-pass false positives are rejected before the answer is allowed to remain in `project_grounded`.

## 12. V2.4 Eval And Observability Notes

- Added an internal retrieval evaluation service and CLI runner:
  - `app.services.retrieval_eval_service`
  - `scripts/run_retrieval_eval.py`
- The eval suite seeds a local DOCX fixture and records, per case:
  - grounded candidate status
  - second-pass trigger status
  - hit count
  - packed hit count
  - retrieval diagnostics
  - grounded-delivery diagnostics
- These diagnostics remain internal and are intentionally not exposed through public API payloads or frontend SSE contracts.
