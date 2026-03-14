CREATE TABLE IF NOT EXISTS _app_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  default_external_policy TEXT NOT NULL CHECK (
    default_external_policy IN ('local_only', 'allow_external')
  ),
  status TEXT NOT NULL CHECK (
    status IN ('active', 'archived')
  ),
  current_snapshot_id TEXT NULL,
  last_activity_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS project_snapshots (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  snapshot_number INTEGER NOT NULL,
  reason TEXT NOT NULL CHECK (
    reason IN (
      'source_ingested',
      'source_refreshed',
      'source_archived',
      'source_deleted',
      'manual_rebuild'
    )
  ),
  status TEXT NOT NULL CHECK (
    status IN ('ready', 'failed', 'superseded')
  ),
  source_count INTEGER NOT NULL,
  indexed_source_count INTEGER NOT NULL,
  low_quality_source_count INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (
    source_type IN ('file_pdf', 'file_docx', 'web_page')
  ),
  title TEXT NOT NULL,
  canonical_uri TEXT NOT NULL,
  original_filename TEXT NULL,
  mime_type TEXT NULL,
  content_hash TEXT NULL,
  ingestion_status TEXT NOT NULL CHECK (
    ingestion_status IN (
      'pending',
      'processing',
      'ready',
      'ready_low_quality',
      'failed',
      'archived'
    )
  ),
  quality_level TEXT NOT NULL CHECK (
    quality_level IN ('normal', 'low')
  ),
  refresh_strategy TEXT NOT NULL CHECK (
    refresh_strategy IN ('manual', 'none')
  ),
  last_refreshed_at TEXT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT NULL,
  deleted_at TEXT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS source_chunks (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  qdrant_point_id TEXT NOT NULL UNIQUE,
  section_label TEXT NOT NULL,
  section_type TEXT NOT NULL DEFAULT 'body',
  heading_path TEXT NULL,
  field_label TEXT NULL,
  table_origin TEXT NULL,
  proposition_type TEXT NULL,
  chunk_index INTEGER NOT NULL,
  token_count INTEGER NOT NULL,
  char_count INTEGER NOT NULL,
  normalized_text TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  retrieval_enabled INTEGER NOT NULL CHECK (retrieval_enabled IN (0, 1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS source_chunk_fts USING fts5(
  chunk_id UNINDEXED,
  project_id UNINDEXED,
  snapshot_id UNINDEXED,
  title,
  normalized_text
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NULL,
  title_source TEXT NOT NULL CHECK (
    title_source IN ('pending', 'auto', 'manual')
  ),
  status TEXT NOT NULL CHECK (
    status IN ('active', 'deleted')
  ),
  latest_message_at TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS session_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  seq_no INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (
    role IN ('user', 'assistant', 'system')
  ),
  message_type TEXT NOT NULL CHECK (
    message_type IN (
      'user_prompt',
      'assistant_answer',
      'status_card',
      'summary_card',
      'report_card',
      'source_update'
    )
  ),
  title TEXT NULL,
  content_md TEXT NOT NULL,
  source_mode TEXT NULL CHECK (
    source_mode IN ('project_grounded', 'weak_source_mode')
  ),
  evidence_status TEXT NULL CHECK (
    evidence_status IN ('grounded', 'insufficient', 'conflicting')
  ),
  disclosure_note TEXT NULL,
  status_label TEXT NULL,
  supports_summary INTEGER NOT NULL DEFAULT 0 CHECK (supports_summary IN (0, 1)),
  supports_report INTEGER NOT NULL DEFAULT 0 CHECK (supports_report IN (0, 1)),
  related_message_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (related_message_id) REFERENCES session_messages(id)
);

CREATE TABLE IF NOT EXISTS message_sources (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  source_id TEXT NULL,
  source_kind TEXT NOT NULL DEFAULT 'project_source' CHECK (
    source_kind IN ('project_source', 'external_web')
  ),
  chunk_id TEXT NULL,
  source_rank INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  source_title TEXT NOT NULL,
  canonical_uri TEXT NOT NULL,
  external_uri TEXT NULL,
  location_label TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  relevance_score REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (message_id) REFERENCES session_messages(id),
  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (chunk_id) REFERENCES source_chunks(id)
);

CREATE TABLE IF NOT EXISTS memory_entries (
  id TEXT PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (
    scope_type IN ('session', 'project')
  ),
  scope_id TEXT NOT NULL,
  topic TEXT NOT NULL,
  fact_text TEXT NOT NULL,
  salience REAL NOT NULL,
  source_message_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_used_at TEXT NULL,
  UNIQUE(scope_type, scope_id, topic, fact_text),
  FOREIGN KEY (source_message_id) REFERENCES session_messages(id)
);
