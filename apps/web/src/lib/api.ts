export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type ProjectSummary = {
  id: string;
  name: string;
  description: string;
  default_external_policy: "local_only" | "allow_external";
  status: "active" | "archived";
  current_snapshot_id: string | null;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  active_session_count: number;
  active_source_count: number;
  latest_session_id: string | null;
  latest_session_title: string | null;
};

export type SessionSummary = {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  title_source: "pending" | "auto" | "manual";
  status: "active" | "deleted";
  latest_message_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  message_count: number;
};

export type MessageSource = {
  id: string;
  source_id: string | null;
  source_kind: "project_source" | "external_web";
  chunk_id: string | null;
  source_rank: number;
  source_type: "web_page" | "file_pdf" | "file_docx";
  source_title: string;
  canonical_uri: string;
  external_uri: string | null;
  location_label: string;
  excerpt: string;
  relevance_score: number;
};

export type ChatMessage = {
  id: string;
  session_id: string;
  project_id: string;
  seq_no: number;
  role: "user" | "assistant" | "system";
  message_type:
    | "user_prompt"
    | "assistant_answer"
    | "status_card"
    | "summary_card"
    | "report_card"
    | "source_update";
  title: string | null;
  content_md: string;
  source_mode: "project_grounded" | "weak_source_mode" | null;
  evidence_status: "grounded" | "insufficient" | "conflicting" | null;
  disclosure_note: string | null;
  status_label: string | null;
  supports_summary: boolean;
  supports_report: boolean;
  related_message_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  sources: MessageSource[];
};

export type SessionDetail = SessionSummary & {
  messages: ChatMessage[];
};

export type KnowledgeSource = {
  id: string;
  project_id: string;
  project_name: string;
  source_type: "web_page" | "file_pdf" | "file_docx";
  title: string;
  canonical_uri: string;
  original_filename: string | null;
  mime_type: string | null;
  ingestion_status: "pending" | "processing" | "ready" | "ready_low_quality" | "failed" | "archived";
  quality_level: "normal" | "low";
  refresh_strategy: "manual" | "none";
  last_refreshed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  deleted_at: string | null;
  favicon_url: string | null;
  match_excerpt?: string;
};

export type SourcePreviewChunk = {
  id: string;
  location_label: string;
  section_type: string;
  heading_path: string | null;
  field_label: string | null;
  table_origin: string | null;
  proposition_type: string | null;
  excerpt: string;
  normalized_text: string;
  char_count: number;
};

export type SourcePreview = KnowledgeSource & {
  preview_chunks: SourcePreviewChunk[];
};

export type SessionGroup = {
  project_id: string;
  project_name: string;
  items: SessionSummary[];
};

export type KnowledgeGroup = {
  project_id: string;
  project_name: string;
  items: KnowledgeSource[];
};

export type StreamedMessageEvent =
  | { event: "delta"; data: { delta: string } }
  | { event: "status"; data: { message: ChatMessage } }
  | { event: "done"; data: { message: ChatMessage } }
  | { event: "error"; data: { message: string } };

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listProjects(input?: {
  includeArchived?: boolean;
  query?: string;
}): Promise<ProjectSummary[]> {
  const params = new URLSearchParams();
  params.set("include_archived", input?.includeArchived ? "true" : "false");
  if (input?.query) {
    params.set("query", input.query);
  }
  const response = await fetch(`${apiBaseUrl}/api/v1/projects?${params.toString()}`, { cache: "no-store" });
  const payload = await readJson<{ items: ProjectSummary[] }>(response);
  return payload.items;
}

export async function getProject(projectId: string): Promise<ProjectSummary> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}`, { cache: "no-store" });
  const payload = await readJson<{ item: ProjectSummary }>(response);
  return payload.item;
}

export async function createProject(input: {
  name: string;
  description: string;
  default_external_policy: "local_only" | "allow_external";
}): Promise<ProjectSummary> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const payload = await readJson<{ item: ProjectSummary }>(response);
  return payload.item;
}

export async function listProjectSessions(projectId: string): Promise<SessionSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/sessions`, { cache: "no-store" });
  const payload = await readJson<{ items: SessionSummary[] }>(response);
  return payload.items;
}

export async function listSessionGroups(): Promise<SessionGroup[]> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions`, { cache: "no-store" });
  const payload = await readJson<{ groups: SessionGroup[] }>(response);
  return payload.groups;
}

export async function createSession(projectId: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/sessions`, {
    method: "POST",
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${sessionId}`, { cache: "no-store" });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function renameSession(sessionId: string, title: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to delete session: ${response.status}`);
  }
}

export async function sendSessionMessage(input: {
  sessionId: string;
  content: string;
  deepResearch: boolean;
  webBrowsing: boolean;
}): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${input.sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: input.content,
      deep_research: input.deepResearch,
      web_browsing: input.webBrowsing,
    }),
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function streamSessionMessage(
  input: {
    sessionId: string;
    content: string;
    deepResearch: boolean;
    webBrowsing: boolean;
  },
  handlers: {
    onEvent: (event: StreamedMessageEvent) => void;
  },
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${input.sessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: input.content,
      deep_research: input.deepResearch,
      web_browsing: input.webBrowsing,
    }),
  });

  if (!response.ok || !response.body) {
    const detail = await response.text();
    throw new Error(detail || `Streaming request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event) {
        handlers.onEvent(event);
      }
    }
  }

  const tail = decoder.decode();
  if (tail) {
    buffer += tail;
  }
  if (buffer.trim()) {
    const event = parseSseEvent(buffer);
    if (event) {
      handlers.onEvent(event);
    }
  }
}

export async function createSummaryCard(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${sessionId}/summary`, {
    method: "POST",
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function createReportCard(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sessions/${sessionId}/report`, {
    method: "POST",
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function deleteMessageCard(messageId: string): Promise<SessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/v1/messages/${messageId}`, {
    method: "DELETE",
  });
  const payload = await readJson<{ item: SessionDetail }>(response);
  return payload.item;
}

export async function listKnowledge(input?: {
  query?: string;
  projectId?: string;
  includeArchived?: boolean;
}): Promise<KnowledgeGroup[]> {
  const params = new URLSearchParams();
  if (input?.query) {
    params.set("query", input.query);
  }
  if (input?.projectId) {
    params.set("project_id", input.projectId);
  }
  params.set("include_archived", input?.includeArchived ? "true" : "false");
  const response = await fetch(`${apiBaseUrl}/api/v1/knowledge?${params.toString()}`, { cache: "no-store" });
  const payload = await readJson<{ groups: KnowledgeGroup[] }>(response);
  return payload.groups;
}

export async function listProjectSources(projectId: string, includeArchived = false): Promise<KnowledgeSource[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/sources?include_archived=${includeArchived ? "true" : "false"}`,
    { cache: "no-store" },
  );
  const payload = await readJson<{ items: KnowledgeSource[] }>(response);
  return payload.items;
}

export async function getSourcePreview(sourceId: string): Promise<SourcePreview> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}`, { cache: "no-store" });
  const payload = await readJson<{ item: SourcePreview }>(response);
  return payload.item;
}

export async function createWebSource(input: {
  projectId: string;
  url: string;
  sessionId?: string;
}): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${input.projectId}/sources/web`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: input.url,
      session_id: input.sessionId ?? null,
    }),
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

export async function createFileSources(input: {
  projectId: string;
  files: File[];
  sessionId?: string;
}): Promise<KnowledgeSource[]> {
  const formData = new FormData();
  input.files.forEach((file) => formData.append("files", file));
  if (input.sessionId) {
    formData.append("session_id", input.sessionId);
  }
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${input.projectId}/sources/files`, {
    method: "POST",
    body: formData,
  });
  const payload = await readJson<{ items: KnowledgeSource[] }>(response);
  return payload.items;
}

export async function updateWebSource(sourceId: string, url: string): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}/web`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

export async function refreshSource(sourceId: string): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}/refresh`, {
    method: "POST",
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

export async function archiveSource(sourceId: string): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}/archive`, {
    method: "POST",
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

export async function restoreSource(sourceId: string): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}/restore`, {
    method: "POST",
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

export async function deleteSource(sourceId: string): Promise<KnowledgeSource> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sources/${sourceId}`, {
    method: "DELETE",
  });
  const payload = await readJson<{ item: KnowledgeSource }>(response);
  return payload.item;
}

function parseSseEvent(raw: string): StreamedMessageEvent | null {
  const lines = raw.split("\n");
  let eventName = "";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventName = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataLines.push(line.slice(6));
    }
  }

  if (!eventName || !dataLines.length) {
    return null;
  }

  const data = JSON.parse(dataLines.join("\n")) as StreamedMessageEvent["data"];
  if (eventName === "delta" || eventName === "status" || eventName === "done" || eventName === "error") {
    return { event: eventName, data } as StreamedMessageEvent;
  }
  return null;
}
