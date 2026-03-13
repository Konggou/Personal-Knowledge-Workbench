"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import type { KnowledgeGroup, KnowledgeSource, ProjectSummary, SourcePreview } from "@/lib/api";
import {
  archiveSource,
  createFileSources,
  createSession,
  createWebSource,
  deleteSource,
  getSourcePreview,
  refreshSource,
  restoreSource,
  updateWebSource,
} from "@/lib/api";

import styles from "./knowledge-page-client.module.css";

type KnowledgePageClientProps = {
  initialGroups: KnowledgeGroup[];
  projects: ProjectSummary[];
  initialProjectId?: string;
  initialQuery: string;
  includeArchived: boolean;
};

type DrawerState =
  | { mode: "none" }
  | { mode: "preview"; item: SourcePreview };

export function KnowledgePageClient({
  initialGroups,
  projects,
  initialProjectId,
  initialQuery,
  includeArchived,
}: KnowledgePageClientProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [groups, setGroups] = useState(initialGroups);
  const [query, setQuery] = useState(initialQuery);
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId ?? "");
  const [showArchived, setShowArchived] = useState(includeArchived);
  const [drawer, setDrawer] = useState<DrawerState>({ mode: "none" });
  const [webInputProjectId, setWebInputProjectId] = useState<string | null>(initialProjectId ?? null);
  const [webUrl, setWebUrl] = useState("");
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);

  useEffect(() => {
    setGroups(initialGroups);
  }, [initialGroups]);

  useEffect(() => {
    setShowArchived(includeArchived);
  }, [includeArchived]);

  const projectOptions = useMemo(() => projects.map((project) => ({ value: project.id, label: project.name })), [projects]);
  const visibleGroups = useMemo(() => {
    if (!selectedProjectId) {
      return groups;
    }
    const existing = groups.find((group) => group.project_id === selectedProjectId);
    if (existing) {
      return groups;
    }
    const project = projects.find((item) => item.id === selectedProjectId);
    if (!project) {
      return groups;
    }
    return [
      {
        project_id: project.id,
        project_name: project.name,
        items: [],
      },
      ...groups,
    ];
  }, [groups, projects, selectedProjectId]);

  function applyFilters() {
    startTransition(() => {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("query", query.trim());
      }
      if (selectedProjectId) {
        params.set("projectId", selectedProjectId);
      }
      if (showArchived) {
        params.set("includeArchived", "true");
      }
      router.push(`/knowledge${params.toString() ? `?${params.toString()}` : ""}`);
    });
  }

  async function openPreview(sourceId: string) {
    const item = await getSourcePreview(sourceId);
    setDrawer({ mode: "preview", item });
  }

  async function handleCreateWebSource(projectId: string) {
    if (!webUrl.trim()) {
      return;
    }
    setSourceError(null);
    try {
      const created = await createWebSource({ projectId, url: webUrl.trim() });
      setGroups((previous) => {
        const next = [...previous];
        const index = next.findIndex((group) => group.project_id === projectId);
        if (index >= 0) {
          next[index] = {
            ...next[index],
            items: [created, ...next[index].items],
          };
          return next;
        }
        const project = projects.find((item) => item.id === projectId);
        return [
          {
            project_id: projectId,
            project_name: project?.name ?? created.project_name,
            items: [created],
          },
          ...next,
        ];
      });
      setWebUrl("");
      setWebInputProjectId(null);
      router.refresh();
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "添加网页资料失败，请稍后重试。");
    }
  }

  async function handleCreateFileSources(projectId: string, files: File[] | null) {
    if (!files?.length) {
      return;
    }
    const unsupported = files.find((file) => !isSupportedFileName(file.name));
    if (unsupported) {
      setSourceError(`当前仅支持 PDF 和 DOCX 文件，暂不支持 ${unsupported.name}。`);
      return;
    }
    setSourceError(null);
    try {
      const created = await createFileSources({ projectId, files });
      setGroups((previous) => {
        const next = [...previous];
        const index = next.findIndex((group) => group.project_id === projectId);
        if (index >= 0) {
          next[index] = {
            ...next[index],
            items: [...created, ...next[index].items],
          };
          return next;
        }
        const project = projects.find((item) => item.id === projectId);
        return [
          {
            project_id: projectId,
            project_name: project?.name ?? "",
            items: created,
          },
          ...next,
        ];
      });
      router.refresh();
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "添加文件资料失败，请稍后重试。");
    }
  }

  async function handleSourceAction(action: "refresh" | "archive" | "restore" | "delete", source: KnowledgeSource) {
    setBusySourceId(source.id);
    try {
      if (action === "refresh") {
        await refreshSource(source.id);
      } else if (action === "archive") {
        await archiveSource(source.id);
      } else if (action === "restore") {
        await restoreSource(source.id);
      } else {
        await deleteSource(source.id);
      }
      router.refresh();
    } finally {
      setBusySourceId(null);
    }
  }

  async function handleEditWebSource(source: KnowledgeSource) {
    if (source.source_type !== "web_page") {
      return;
    }
    const nextUrl = window.prompt("新的网页链接", source.canonical_uri)?.trim();
    if (!nextUrl) {
      return;
    }
    setBusySourceId(source.id);
    try {
      const updated = await updateWebSource(source.id, nextUrl);
      setGroups((previous) =>
        previous.map((group) => ({
          ...group,
          items: group.items.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
        })),
      );
      if (drawer.mode === "preview" && drawer.item.id === source.id) {
        setDrawer({ mode: "preview", item: await getSourcePreview(source.id) });
      }
      router.refresh();
    } finally {
      setBusySourceId(null);
    }
  }

  async function handleEnterChat(projectId: string) {
    const session = await createSession(projectId);
    router.push(`/projects/${projectId}?sessionId=${session.id}`);
  }

  return (
    <div className={styles.page}>
      <section className={styles.filters}>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              applyFilters();
            }
          }}
          placeholder="搜索资料标题或命中内容"
        />
        <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>
          <option value="">全部项目</option>
          {projectOptions.map((project) => (
            <option key={project.value} value={project.value}>
              {project.label}
            </option>
          ))}
        </select>
        <label className={styles.archiveToggle}>
          <input checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} type="checkbox" />
          <span>显示已归档资料</span>
        </label>
        <button disabled={isPending} onClick={applyFilters} type="button">
          应用筛选
        </button>
      </section>

      {sourceError ? <div className={styles.errorBanner}>{sourceError}</div> : null}

      <div className={styles.layout}>
        <div className={styles.groups}>
          {visibleGroups.map((group) => (
            <section key={group.project_id} className={styles.groupCard}>
              <div className={styles.groupHeader}>
                <div>
                  <h2 className={styles.groupTitle}>{group.project_name}</h2>
                  <p className={styles.groupMeta}>{group.items.length} 份资料</p>
                </div>
                <div className={styles.groupActions}>
                  <label className={styles.fileButton}>
                    添加文件
                    <input
                      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      hidden
                      multiple
                      onChange={(event) => {
                        const nextFiles = event.currentTarget.files ? Array.from(event.currentTarget.files) : null;
                        event.currentTarget.value = "";
                        void handleCreateFileSources(group.project_id, nextFiles);
                      }}
                      type="file"
                    />
                  </label>
                  <button onClick={() => setWebInputProjectId(group.project_id)} type="button">
                    添加网页链接
                  </button>
                </div>
              </div>

              {webInputProjectId === group.project_id ? (
                <div className={styles.webForm}>
                  <input value={webUrl} onChange={(event) => setWebUrl(event.target.value)} placeholder="https://example.com/article" />
                  <button onClick={() => void handleCreateWebSource(group.project_id)} type="button">
                    保存
                  </button>
                </div>
              ) : null}

              <div className={styles.sourceList}>
                {group.items.map((item) => (
                  <article key={item.id} className={styles.sourceCard}>
                    <button className={styles.sourceMain} onClick={() => void openPreview(item.id)} type="button">
                      <strong>{item.title}</strong>
                      <span>
                        {item.source_type === "web_page" ? item.canonical_uri : item.original_filename ?? item.canonical_uri}
                      </span>
                      {item.match_excerpt ? <em>{item.match_excerpt}</em> : null}
                    </button>
                    <div className={styles.sourceActions}>
                      {item.source_type === "web_page" ? (
                        <button disabled={busySourceId === item.id} onClick={() => void handleEditWebSource(item)} type="button">
                          改链接
                        </button>
                      ) : null}
                      {item.source_type === "web_page" ? (
                        <button disabled={busySourceId === item.id} onClick={() => void handleSourceAction("refresh", item)} type="button">
                          刷新
                        </button>
                      ) : null}
                      {item.ingestion_status === "archived" ? (
                        <button disabled={busySourceId === item.id} onClick={() => void handleSourceAction("restore", item)} type="button">
                          恢复
                        </button>
                      ) : (
                        <button disabled={busySourceId === item.id} onClick={() => void handleSourceAction("archive", item)} type="button">
                          归档
                        </button>
                      )}
                      <button disabled={busySourceId === item.id} onClick={() => void handleSourceAction("delete", item)} type="button">
                        删除
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}

          {!visibleGroups.length ? <div className={styles.emptyState}>当前没有命中的资料。先创建项目，再把网页或文件导入知识库。</div> : null}
        </div>

        <aside className={`${styles.drawer} ${drawer.mode === "none" ? styles.drawerHidden : ""}`.trim()}>
          {drawer.mode === "preview" ? (
            <div className={styles.previewPanel}>
              <div className={styles.previewHeader}>
                <div>
                  <p className={styles.previewEyebrow}>来源预览</p>
                  <h3>{drawer.item.title}</h3>
                </div>
                <button onClick={() => setDrawer({ mode: "none" })} type="button">
                  关闭
                </button>
              </div>
              <p className={styles.previewLink}>{drawer.item.canonical_uri}</p>
              <div className={styles.previewChunks}>
                {drawer.item.preview_chunks.map((chunk) => {
                  const context = renderPreviewChunkContext(chunk);
                  return (
                    <article key={chunk.id} className={styles.chunkCard}>
                      <strong>{chunk.location_label}</strong>
                      {context ? <span className={styles.chunkMeta}>{context}</span> : null}
                      <p>{chunk.normalized_text}</p>
                    </article>
                  );
                })}
              </div>
              <div className={styles.previewFooter}>
                <button onClick={() => void handleEnterChat(drawer.item.project_id)} type="button">
                  进入聊天
                </button>
                <Link href={`/projects/${drawer.item.project_id}`}>打开项目</Link>
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function isSupportedFileName(name: string) {
  const lower = name.toLowerCase();
  return lower.endsWith(".pdf") || lower.endsWith(".docx");
}

function normalizeSourceError(message: string) {
  if (message.includes("Unsupported file type")) {
    return "当前仅支持 PDF 和 DOCX 文件，暂不支持旧版 DOC 文件。";
  }
  return message;
}

function renderPreviewChunkContext(chunk: SourcePreview["preview_chunks"][number]) {
  const parts = [chunk.heading_path, chunk.field_label].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
