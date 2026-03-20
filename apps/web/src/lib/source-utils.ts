import type { SourcePreview } from "@/lib/api";

export function isSupportedFileName(name: string) {
  const lower = name.toLowerCase();
  return lower.endsWith(".pdf") || lower.endsWith(".docx");
}

export function normalizeSourceError(message: string) {
  if (message.includes("Unsupported file type")) {
    return "当前仅支持 PDF 和 DOCX 文件，暂不支持旧版 DOC 文件。";
  }
  return message;
}

export function renderPreviewChunkContext(chunk: SourcePreview["preview_chunks"][number]) {
  const parts = [chunk.heading_path, chunk.field_label].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
