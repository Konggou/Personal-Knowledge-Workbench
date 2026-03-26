# 个人知识工作台后端结构

## 1. 目标

本文定义后端稳定结构：服务边界、数据模型、公开 API、存储约束与运行时不变量。

版本演进历史、阶段性实验和完成记录不放在本文，统一参考 `progress.txt`。

## 2. 后端原则

- 前台公开语义统一为：项目 / 会话 / 消息 / 知识库 / 来源
- 不再把 `task` 作为前台对象暴露
- SQLite 是唯一结构化状态中心
- Qdrant 是默认向量检索后端
- 删除遵循软删除语义
- 聊天主链服务于项目内对话，不反向塑造 task-first 体验
- 来源层只代表最终证据集，不暴露召回候选或内部 rerank 细节

## 3. 服务边界

### 3.1 ProjectService

职责：

- 创建、读取、列出、归档项目
- 返回项目聚合信息

典型聚合字段：

- `active_session_count`
- `active_source_count`
- `latest_session_id`
- `latest_session_title`
- `last_activity_at`

### 3.2 SessionService

职责：

- 创建、列出、重命名、删除会话
- 维护会话级元数据与聚合视图
- 管理摘要卡、报告卡等结果型消息入口

### 3.3 SessionTurnService

职责：

- 编排单轮消息生命周期
- 写入用户消息、助手消息、状态卡
- 管理流式输出持久化
- 挂载最终来源集

### 3.4 SourceService

职责：

- 项目内来源列表与详情
- 文件、网页导入
- 网页刷新、改链、归档、恢复、删除
- 入库后同步结构化索引与向量索引
- 可选写入 `source update` 系统消息

### 3.5 KnowledgeService

职责：

- 全局资料浏览
- 全局资料搜索
- 按项目分组返回资料

### 3.6 SearchService

职责：

- 词法检索
- 语义检索
- 混合召回
- rerank
- grounded 候选组装

### 3.7 GroundedGenerationService

职责：

- 接收最终候选证据集
- 进行证据选择、压缩与 evidence pack 组装
- 生成结构化 grounded answer
- 在失败时执行有边界的降级

### 3.8 AgentOrchestratorService

职责：

- 组织普通聊天、深度调研、联网补充的内部执行路径
- 统一证据模式判定与 pre-answer 检查

关键规则：

- 普通 grounded 复杂问题只触发 rerank，不自动升级为深度调研
- 深度调研只有在用户显式开启时才进入研究型路径
- 联网补充只在用户显式开启时才允许引入网页证据

### 3.9 SettingsService

职责：

- 读取全局模型与检索配置
- 保存运行时设置
- 管理 API Key 与默认值
- 说明配置何时生效

## 4. 证据模式

当前稳定公开语义主要落在以下模式：

- `project_grounded`：项目资料足够，答案以项目资料为主
- `weak_source_mode`：项目资料偏弱或不足，但仍维持会话内正常回答流程

相关补充状态：

- `evidence_status=insufficient`：当前证据不足，无法形成完整结论

联网补充与更细的网页证据主导模式仍属于运行时演进方向，不应在本文写成已全面落地的公开合同。

要求：

- readiness check 与生成提示词必须基于同一模式
- `message_sources` 只保存最终证据集
- 前台来源层不展示内部检索过程

## 5. 存储

### 5.1 SQLite

SQLite 保存全部结构化状态：

- 项目
- 会话
- 消息
- 来源
- source chunks
- FTS 索引
- message-source 关系
- memory entries
- 应用元数据

### 5.2 Qdrant

Qdrant 负责向量检索，默认使用 embedded 模式，便于本地运行。

## 6. 关键 Schema 摘要

### 6.1 `_app_metadata`

用途：

- 保存 schema version
- 保存检索相关版本信息
- 保存全局模型设置等运行时配置

### 6.2 `projects`

关键字段：

- `id`
- `name`
- `description`
- `default_external_policy`
- `status`
- `last_activity_at`
- `created_at`
- `updated_at`
- `archived_at`

### 6.3 `sources`

关键字段：

- `id`
- `project_id`
- `source_type`
- `title`
- `canonical_uri`
- `ingestion_status`
- `quality_level`
- `refresh_strategy`
- `error_code`
- `error_message`
- `created_at`
- `updated_at`
- `archived_at`
- `deleted_at`

### 6.4 `source_chunks`

关键字段：

- `id`
- `source_id`
- `project_id`
- `snapshot_id`
- `chunk_index`
- `section_label`
- `section_type`
- `heading_path`
- `field_label`
- `table_origin`
- `proposition_type`
- `normalized_text`
- `excerpt`
- `retrieval_enabled`

### 6.5 `sessions`

关键字段：

- `id`
- `project_id`
- `title`
- `title_source`
- `status`
- `latest_message_at`
- `created_at`
- `updated_at`
- `deleted_at`

### 6.6 `session_messages`

关键字段：

- `id`
- `session_id`
- `project_id`
- `seq_no`
- `role`
- `message_type`
- `title`
- `content_md`
- `source_mode`
- `evidence_status`
- `disclosure_note`
- `status_label`
- `supports_summary`
- `supports_report`
- `related_message_id`
- `created_at`
- `updated_at`
- `deleted_at`

### 6.7 `message_sources`

关键字段：

- `id`
- `message_id`
- `session_id`
- `project_id`
- `source_kind`
- `source_id`
- `chunk_id`
- `external_uri`
- `source_rank`
- `source_type`
- `source_title`
- `canonical_uri`
- `location_label`
- `excerpt`
- `relevance_score`

约束：

- `source_kind` 只承载最终来源类型，如 `project_source` 或 `external_web`
- `external_uri` 用于网页补充来源

### 6.8 `memory_entries`

用途：

- 保存会话或项目范围的轻量记忆条目

## 7. 公开 API

### 7.1 Projects

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`

### 7.2 Sessions

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

### 7.3 Knowledge

- `GET /api/v1/knowledge`

### 7.4 Sources

- `GET /api/v1/projects/{project_id}/sources`
- `POST /api/v1/projects/{project_id}/sources/web`
- `POST /api/v1/projects/{project_id}/sources/files`
- `GET /api/v1/sources/{source_id}`
- `PATCH /api/v1/sources/{source_id}/web`
- `POST /api/v1/sources/{source_id}/refresh`
- `POST /api/v1/sources/{source_id}/archive`
- `POST /api/v1/sources/{source_id}/restore`
- `DELETE /api/v1/sources/{source_id}`

### 7.5 Settings

- `GET /api/v1/settings/models`
- `PUT /api/v1/settings/models`

### 7.6 Admin

- `POST /api/v1/admin/cleanup`
- `GET /api/v1/admin/cleanup/preview`

## 8. 删除与清理

- 项目删除：前台表现为归档或软删除，超过保留窗口后由清理服务物理清除
- 会话删除：软删除
- 来源删除：软删除
- 结果卡删除：软删除
- 来源归档：退出主检索，但保留记录

CleanupService 负责：

- 清理超过窗口期的归档项目与关联数据
- 同步清理消息、来源、chunks 与向量索引
- 提供手动触发与预览接口

## 9. 检索与生成不变量

- 检索默认走混合召回：词法 + 语义 + RRF
- rerank 是普通 grounded 路径中的条件步骤
- 低命中时允许有限二次召回，但不改变公开语义
- 生成只消费最终证据集，不直接暴露中间候选
- 结构化输出失败时可降级，但必须保留清晰的证据状态

## 10. 前后端边界

- 前台不得依赖旧 task API
- 前台只消费项目、会话、知识库、来源、设置等公开对象
- 前台来源层可以使用覆盖式预览，但不改变后端对象模型
- 后端内部即使使用 task-like orchestration，也必须完全隐藏在实现内
