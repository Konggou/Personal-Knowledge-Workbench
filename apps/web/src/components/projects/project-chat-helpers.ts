import type { ChatMessage, SessionSummary } from "@/lib/api";

export function sortSessions(a: SessionSummary, b: SessionSummary) {
  return (b.latest_message_at ?? b.updated_at).localeCompare(a.latest_message_at ?? a.updated_at);
}

export function createTemporaryMessage(input: {
  id: string;
  sessionId: string;
  projectId: string;
  role: ChatMessage["role"];
  messageType: ChatMessage["message_type"];
  content: string;
  title?: string | null;
  sourceMode?: ChatMessage["source_mode"];
  supportsSummary?: boolean;
  supportsReport?: boolean;
}): ChatMessage {
  const now = new Date().toISOString();
  return {
    id: input.id,
    session_id: input.sessionId,
    project_id: input.projectId,
    seq_no: Number.MAX_SAFE_INTEGER,
    role: input.role,
    message_type: input.messageType,
    title: input.title ?? null,
    content_md: input.content,
    source_mode: input.sourceMode ?? null,
    evidence_status: null,
    disclosure_note: null,
    status_label: null,
    supports_summary: input.supportsSummary ?? false,
    supports_report: input.supportsReport ?? false,
    related_message_id: null,
    created_at: now,
    updated_at: now,
    deleted_at: null,
    sources: [],
  };
}

export function projectInitials(name: string) {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 2) || "PK"
  );
}

export function sourceIconFor(item: { source_type: string; canonical_uri: string }) {
  if (item.source_type !== "web_page") {
    return null;
  }
  try {
    return `https://www.google.com/s2/favicons?sz=64&domain=${new URL(item.canonical_uri).hostname}`;
  } catch {
    return null;
  }
}

export function summarizeSourceKinds(sources: ChatMessage["sources"]) {
  const projectCount = sources.filter((source) => source.source_kind === "project_source").length;
  const webCount = sources.filter((source) => source.source_kind === "external_web").length;

  if (projectCount && webCount) {
    return `${sources.length} 个来源 · 项目 ${projectCount} / 网页 ${webCount}`;
  }
  if (webCount) {
    return `${webCount} 个网页来源`;
  }
  return `${projectCount || sources.length} 个项目来源`;
}

export function formatSourceHost(uri: string) {
  try {
    return new URL(uri).host;
  } catch {
    return uri;
  }
}
