"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage, KnowledgeSource, ProjectSummary, SessionDetail, SessionGroup, SessionSummary, SourcePreview } from "@/lib/api";
import {
  createFileSources,
  createReportCard,
  createSession,
  createSummaryCard,
  createWebSource,
  deleteMessageCard,
  deleteSession,
  getSession,
  getSourcePreview,
  listProjectSources,
  renameSession,
  streamSessionMessage,
} from "@/lib/api";

import styles from "./project-chat-client.module.css";

type ProjectChatClientProps = {
  project: ProjectSummary;
  allProjects: ProjectSummary[];
  initialSessionGroups: SessionGroup[];
  initialSelectedSession: SessionDetail | null;
  initialSources: KnowledgeSource[];
};

export function ProjectChatClient({
  project,
  allProjects,
  initialSessionGroups,
  initialSelectedSession,
  initialSources,
}: ProjectChatClientProps) {
  const router = useRouter();
  const [isPending] = useTransition();
  const [projects, setProjects] = useState(allProjects);
  const [sessionGroups, setSessionGroups] = useState(initialSessionGroups);
  const [selectedSession, setSelectedSession] = useState(initialSelectedSession);
  const [sources, setSources] = useState(initialSources);
  const [previewSource, setPreviewSource] = useState<SourcePreview | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({ [project.id]: true });
  const [message, setMessage] = useState("");
  const [deepResearch, setDeepResearch] = useState(false);
  const [webBrowsing, setWebBrowsing] = useState(false);
  const [showAddSourceMenu, setShowAddSourceMenu] = useState(false);
  const [showWebForm, setShowWebForm] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [expandedSourceLists, setExpandedSourceLists] = useState<Record<string, boolean>>({});
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [isStreamingMessage, setIsStreamingMessage] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputId = `project-chat-file-input-${project.id}`;

  const currentProjectSessions = useMemo(
    () => sessionGroups.find((group) => group.project_id === project.id)?.items ?? [],
    [project.id, sessionGroups],
  );

  const latestActionableMessage = useMemo(() => {
    if (!selectedSession) {
      return null;
    }
    return [...selectedSession.messages]
      .reverse()
      .find((item) => item.message_type === "assistant_answer" && item.supports_report);
  }, [selectedSession]);

  const weakSourceMode = sources.length === 0;

  useEffect(() => {
    setBusySessionId(null);
  }, [project.id, selectedSession?.id]);

  const projectTree = useMemo(() => {
    return projects.map((item) => ({
      ...item,
      sessions: sessionGroups.find((group) => group.project_id === item.id)?.items ?? [],
      expanded: expandedProjects[item.id] ?? item.id === project.id,
    }));
  }, [expandedProjects, project.id, projects, sessionGroups]);

  function upsertProjectSessions(projectId: string, nextItems: SessionSummary[]) {
    setSessionGroups((previous) => {
      const others = previous.filter((group) => group.project_id !== projectId);
      const projectName = projects.find((item) => item.id === projectId)?.name ?? project.name;
      if (!nextItems.length) {
        return others;
      }
      return [...others, { project_id: projectId, project_name: projectName, items: nextItems }];
    });
    setProjects((previous) =>
      previous.map((item) =>
        item.id === projectId
          ? {
              ...item,
              active_session_count: nextItems.length,
              latest_session_id: nextItems[0]?.id ?? null,
              latest_session_title: nextItems[0]?.title ?? null,
              last_activity_at: nextItems[0]?.latest_message_at ?? item.last_activity_at,
            }
          : item,
      ),
    );
  }

  function syncProjectSourceCount(projectId: string, count: number) {
    setProjects((previous) =>
      previous.map((item) =>
        item.id === projectId
          ? {
              ...item,
              active_source_count: count,
            }
          : item,
      ),
    );
  }

  async function refreshProjectSources() {
    const nextSources = await listProjectSources(project.id);
    setSources(nextSources);
    syncProjectSourceCount(project.id, nextSources.length);
    return nextSources;
  }

  async function refreshSelectedSession(sessionId: string) {
    const next = await getSession(sessionId);
    setSelectedSession(next);
    const nextSessions = currentProjectSessions.map((item) =>
      item.id === next.id
        ? {
            ...item,
            title: next.title,
            title_source: next.title_source,
            message_count: next.message_count,
            latest_message_at: next.latest_message_at,
            updated_at: next.updated_at,
          }
        : item,
    );
    upsertProjectSessions(project.id, nextSessions.sort(sortSessions));
    return next;
  }

  async function handleCreateSession() {
    const session = await createSession(project.id);
    upsertProjectSessions(project.id, [session, ...currentProjectSessions].sort(sortSessions));
    setSelectedSession(session);
    setExpandedProjects((previous) => ({ ...previous, [project.id]: true }));
    router.push(`/projects/${project.id}?sessionId=${session.id}`);
  }

  function handleSelectProject(projectId: string) {
    setExpandedProjects((previous) => ({ ...previous, [projectId]: true }));
    router.push(`/projects/${projectId}`);
  }

  async function handleSelectSession(session: SessionSummary) {
    if (busySessionId === session.id) {
      return;
    }
    setBusySessionId(session.id);
    try {
      if (session.project_id === project.id) {
        const next = await getSession(session.id);
        setSelectedSession(next);
        router.push(`/projects/${session.project_id}?sessionId=${session.id}`);
        return;
      }
      router.push(`/projects/${session.project_id}?sessionId=${session.id}`);
    } finally {
      if (session.project_id !== project.id) {
        setBusySessionId(null);
      }
    }
  }

  function toggleProject(projectId: string) {
    setExpandedProjects((previous) => ({ ...previous, [projectId]: !(previous[projectId] ?? projectId === project.id) }));
  }

  async function handleRenameSession(session: SessionSummary) {
    const title = window.prompt("新的会话名称", session.title)?.trim();
    if (!title) {
      return;
    }
    const updated = await renameSession(session.id, title);
    const nextSessions = currentProjectSessions.map((item) => (item.id === session.id ? { ...item, title: updated.title } : item));
    upsertProjectSessions(project.id, nextSessions);
    if (selectedSession?.id === session.id) {
      setSelectedSession(updated);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    if (!window.confirm("确认删除这条会话吗？")) {
      return;
    }
    await deleteSession(sessionId);
    const nextSessions = currentProjectSessions.filter((item) => item.id !== sessionId);
    upsertProjectSessions(project.id, nextSessions);
    if (selectedSession?.id === sessionId) {
      setSelectedSession(null);
      router.push(`/projects/${project.id}`);
    }
  }

  async function handleSendMessage() {
    if (!selectedSession || !message.trim()) {
      return;
    }
    const sessionId = selectedSession.id;
    const content = message.trim();
    const useDeepResearch = deepResearch;
    const useWebBrowsing = webBrowsing && project.default_external_policy === "allow_external";
    const tempUserMessage = createTemporaryMessage({
      id: `temp-user-${Date.now()}`,
      sessionId,
      projectId: project.id,
      role: "user",
      messageType: "user_prompt",
      content,
    });
    const tempAssistantMessage = createTemporaryMessage({
      id: `temp-assistant-${Date.now()}`,
      sessionId,
      projectId: project.id,
      role: "assistant",
      messageType: "assistant_answer",
      title: useDeepResearch ? "调研结论" : null,
      content: "",
      supportsSummary: true,
      supportsReport: true,
    });

    setSelectedSession((previous) =>
      previous
        ? {
            ...previous,
            messages: [...previous.messages, tempUserMessage, tempAssistantMessage],
            message_count: previous.message_count + 2,
          }
        : previous,
    );
    setMessage("");
    setDeepResearch(false);
    setWebBrowsing(false);
    setIsStreamingMessage(true);
    setActionError(null);
    let streamFailed = false;

    try {
      await streamSessionMessage(
        {
          sessionId,
          content,
          deepResearch: useDeepResearch,
          webBrowsing: useWebBrowsing,
        },
        {
          onEvent: (event) => {
            if (event.event === "delta") {
              setSelectedSession((previous) =>
                previous
                  ? {
                      ...previous,
                      messages: previous.messages.map((item) =>
                        item.id === tempAssistantMessage.id
                          ? { ...item, content_md: `${item.content_md}${event.data.delta}` }
                          : item,
                      ),
                    }
                  : previous,
              );
              return;
            }

            if (event.event === "status") {
              setSelectedSession((previous) =>
                previous
                  ? {
                      ...previous,
                      messages: [...previous.messages, event.data.message],
                      message_count: previous.message_count + 1,
                    }
                  : previous,
              );
              return;
            }

            if (event.event === "done") {
              setSelectedSession((previous) =>
                previous
                  ? {
                      ...previous,
                      messages: previous.messages.map((item) =>
                        item.id === tempAssistantMessage.id ? event.data.message : item,
                      ),
                    }
                  : previous,
              );
              return;
            }

            streamFailed = true;
            setSelectedSession((previous) =>
              previous
                ? {
                    ...previous,
                    messages: previous.messages.map((item) =>
                      item.id === tempAssistantMessage.id
                        ? {
                            ...item,
                            content_md: event.data.message || "生成回复失败，请稍后重试。",
                          }
                        : item,
                    ),
                  }
                : previous,
            );
          },
        },
      );

      if (!streamFailed) {
        const next = await refreshSelectedSession(sessionId);
        const nextSessions = currentProjectSessions
          .map((item) =>
            item.id === next.id
              ? {
                  ...item,
                  title: next.title,
                  title_source: next.title_source,
                  message_count: next.message_count,
                  latest_message_at: next.latest_message_at,
                  updated_at: next.updated_at,
                }
              : item,
          )
          .sort(sortSessions);
        upsertProjectSessions(project.id, nextSessions);
      }
    } catch (caught) {
      setSelectedSession((previous) =>
        previous
          ? {
              ...previous,
              messages: previous.messages.map((item) =>
                item.id === tempAssistantMessage.id
                  ? {
                      ...item,
                      content_md: caught instanceof Error ? caught.message : "发送消息失败，请稍后重试。",
                    }
                  : item,
              ),
            }
          : previous,
      );
    } finally {
      setIsStreamingMessage(false);
    }
  }

  async function handleSaveSummary() {
    if (!selectedSession) {
      return;
    }
    setActionError(null);
    try {
      const next = await createSummaryCard(selectedSession.id);
      setSelectedSession(next);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "保存摘要失败，请稍后重试。");
    }
  }

  async function handleGenerateReport() {
    if (!selectedSession || !latestActionableMessage) {
      return;
    }
    setActionError(null);
    try {
      const next = await createReportCard(selectedSession.id);
      setSelectedSession(next);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "生成报告失败，请稍后重试。");
    }
  }

  async function handleDeleteCard(messageId: string) {
    if (!selectedSession) {
      return;
    }
    const next = await deleteMessageCard(messageId);
    setSelectedSession(next);
  }

  async function handleSaveExternalSource(url: string) {
    if (!selectedSession) {
      return;
    }
    setSourceError(null);
    try {
      await createWebSource({
        projectId: project.id,
        url,
        sessionId: selectedSession.id,
      });
      await refreshProjectSources();
      await refreshSelectedSession(selectedSession.id);
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "保存网页资料失败，请稍后重试。");
    }
  }

  async function handleWebSourceCreate() {
    if (!selectedSession || !webUrl.trim()) {
      return;
    }
    setSourceError(null);
    try {
      await createWebSource({
        projectId: project.id,
        url: webUrl.trim(),
        sessionId: selectedSession.id,
      });
      setWebUrl("");
      setShowWebForm(false);
      setShowAddSourceMenu(false);
      await refreshProjectSources();
      await refreshSelectedSession(selectedSession.id);
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "添加网页资料失败，请稍后重试。");
    }
  }

  async function handleFileSourceCreate(files: File[] | null) {
    if (!selectedSession || !files?.length) {
      return;
    }
    const unsupported = files.find((file) => !isSupportedFileName(file.name));
    if (unsupported) {
      setSourceError(`当前仅支持 PDF 和 DOCX 文件，暂不支持 ${unsupported.name}。`);
      return;
    }
    setSourceError(null);
    try {
      await createFileSources({
        projectId: project.id,
        files,
        sessionId: selectedSession.id,
      });
      setShowAddSourceMenu(false);
      await refreshProjectSources();
      await refreshSelectedSession(selectedSession.id);
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "添加文件资料失败，请稍后重试。");
    }
  }

  async function openSourcePreview(sourceId: string) {
    setPreviewSource(await getSourcePreview(sourceId));
  }

  function toggleSourceList(messageId: string) {
    setExpandedSourceLists((previous) => ({ ...previous, [messageId]: !previous[messageId] }));
  }

  function sourceIconFor(item: { source_type: string; canonical_uri: string }) {
    if (item.source_type === "web_page") {
      try {
        return `https://www.google.com/s2/favicons?sz=64&domain=${new URL(item.canonical_uri).hostname}`;
      } catch {
        return null;
      }
    }
    return null;
  }

  return (
    <div className={styles.shell}>
      <div className={`${styles.layout} ${sidebarCollapsed ? styles.layoutCollapsed : ""}`.trim()}>
        <aside className={`${styles.sidebar} ${sidebarCollapsed ? styles.sidebarCollapsed : ""}`.trim()}>
          <div className={styles.sidebarTop}>
            <button
              aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
              className={styles.collapseButton}
              onClick={() => setSidebarCollapsed((value) => !value)}
              title={sidebarCollapsed ? "展开" : "收起"}
              type="button"
            >
              <span aria-hidden="true" className={styles.collapseGlyph}>
                {sidebarCollapsed ? ">" : "<"}
              </span>
            </button>
            {!sidebarCollapsed ? (
              <button className={styles.newSessionButton} onClick={() => void handleCreateSession()} type="button">
                新建会话
              </button>
            ) : (
              <button aria-label="新建会话" className={styles.railActionButton} onClick={() => void handleCreateSession()} type="button">
                +
              </button>
            )}
          </div>

          {sidebarCollapsed ? (
            <div className={styles.railProjectList}>
              {projectTree.map((item) => (
                <button
                  key={item.id}
                  aria-label={item.name}
                  className={`${styles.railProjectButton} ${item.id === project.id ? styles.railProjectButtonActive : ""}`.trim()}
                  onClick={() => handleSelectProject(item.id)}
                  title={item.name}
                  type="button"
                >
                  {projectInitials(item.name)}
                </button>
              ))}
            </div>
          ) : (
            <div className={styles.projectTree}>
              {projectTree.map((item) => (
                <section key={item.id} className={`${styles.projectSection} ${item.id === project.id ? styles.projectSectionActive : ""}`.trim()}>
                  <div className={styles.projectRow}>
                    <button className={styles.projectButton} onClick={() => handleSelectProject(item.id)} type="button">
                      <span className={styles.projectBadge}>{projectInitials(item.name)}</span>
                      <span className={styles.projectMeta}>
                        <strong>{item.name}</strong>
                        <span>
                          {item.active_source_count} 份资料 · {item.active_session_count} 个会话
                        </span>
                      </span>
                    </button>
                    <button
                      aria-label={item.expanded ? `收起 ${item.name}` : `展开 ${item.name}`}
                      className={styles.projectToggleButton}
                      onClick={() => toggleProject(item.id)}
                      type="button"
                    >
                      {item.expanded ? "−" : "+"}
                    </button>
                  </div>

                  {item.expanded ? (
                    <div className={styles.sessionList}>
                      {item.sessions.length ? (
                        item.sessions.map((session) => (
                          <article
                            key={session.id}
                            className={`${styles.sessionItem} ${selectedSession?.id === session.id ? styles.sessionItemActive : ""}`.trim()}
                          >
                            <button
                              className={styles.sessionSelect}
                              disabled={busySessionId === session.id}
                              onClick={() => void handleSelectSession(session)}
                              type="button"
                            >
                              <strong>{session.title}</strong>
                              <span>{session.message_count} 条消息</span>
                            </button>
                            {item.id === project.id ? (
                              <div className={styles.sessionItemActions}>
                                <button onClick={() => void handleRenameSession(session)} type="button">
                                  重命名
                                </button>
                                <button onClick={() => void handleDeleteSession(session.id)} type="button">
                                  删除
                                </button>
                              </div>
                            ) : null}
                          </article>
                        ))
                      ) : (
                        <div className={styles.sidebarEmpty}>这个项目还没有会话。</div>
                      )}
                    </div>
                  ) : null}
                </section>
              ))}
            </div>
          )}
        </aside>

        <section className={styles.chatStage}>
          {!selectedSession ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyContent}>
                <p className={styles.emptyEyebrow}>项目空态</p>
                <h1>{project.name}</h1>
                <p>{project.description}</p>
                <div className={styles.emptyActions}>
                  <button onClick={() => void handleCreateSession()} type="button">
                    新建会话
                  </button>
                  <Link href={`/knowledge?projectId=${project.id}`}>去知识库添加资料</Link>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className={styles.chatScroll}>
                <div className={styles.chatColumn}>
                  {selectedSession.messages.length ? (
                    <div className={styles.messageStream}>
                      {selectedSession.messages.map((item) => (
                        <MessageCard
                          key={item.id}
                          expanded={!!expandedSourceLists[item.id]}
                          isLatestActionable={latestActionableMessage?.id === item.id}
                          isStreamingMessage={isStreamingMessage}
                          message={item}
                          onDeleteCard={handleDeleteCard}
                          onOpenSource={openSourcePreview}
                          onSaveExternalSource={handleSaveExternalSource}
                          onSaveSummary={handleSaveSummary}
                          onToggleSources={toggleSourceList}
                          sourceIconFor={sourceIconFor}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className={styles.sessionIntro}>
                      <p className={styles.emptyEyebrow}>新会话</p>
                      <h1>{selectedSession.title}</h1>
                      <p>从这个项目里的资料开始提问。需要更完整分析时，可手动开启深度调研。</p>
                    </div>
                  )}
                </div>
              </div>

              <div className={styles.composerDock}>
                <div className={styles.composerColumn}>
                  <div className={styles.composerMetaRow}>
                    <Link className={styles.knowledgeLink} href={`/knowledge?projectId=${project.id}`}>
                      知识库 · {sources.length} 份资料
                    </Link>
                    {weakSourceMode ? <span className={styles.weakSourceNotice}>当前项目还没有可检索资料，这次对话将以弱资料模式进行。</span> : null}
                  </div>

                  {showWebForm ? (
                    <div className={styles.inlineWebForm}>
                      <input
                        onChange={(event) => setWebUrl(event.target.value)}
                        placeholder="https://example.com/article"
                        value={webUrl}
                      />
                      <button onClick={() => void handleWebSourceCreate()} type="button">
                        添加网页
                      </button>
                    </div>
                  ) : null}

                  {sourceError ? <div className={styles.sourceError}>{sourceError}</div> : null}
                  {actionError ? <div className={styles.sourceError}>{actionError}</div> : null}

                  <input
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    hidden
                    id={fileInputId}
                    multiple
                    onChange={(event) => {
                      const nextFiles = event.currentTarget.files ? Array.from(event.currentTarget.files) : null;
                      event.currentTarget.value = "";
                      setShowAddSourceMenu(false);
                      void handleFileSourceCreate(nextFiles);
                    }}
                    ref={fileInputRef}
                    type="file"
                  />

                  <div className={styles.composerSurface}>
                    <div className={styles.composerActionRow}>
                      <div className={styles.addSourceBox}>
                        <button className={styles.lightAction} onClick={() => setShowAddSourceMenu((value) => !value)} type="button">
                          增加资料
                        </button>
                        {showAddSourceMenu ? (
                          <div className={styles.addSourceMenu}>
                            <button
                              onClick={() => {
                                setShowWebForm(true);
                                setShowAddSourceMenu(false);
                              }}
                              type="button"
                            >
                              添加网页链接
                            </button>
                            <button
                              onClick={() => {
                                setShowAddSourceMenu(false);
                                window.setTimeout(() => fileInputRef.current?.click(), 0);
                              }}
                              type="button"
                            >
                              添加文件
                            </button>
                          </div>
                        ) : null}
                      </div>

                      <button
                        aria-pressed={deepResearch}
                        className={`${styles.lightAction} ${deepResearch ? styles.lightActionActive : ""}`.trim()}
                        onClick={() => setDeepResearch((value) => !value)}
                        type="button"
                      >
                        深度调研
                      </button>

                      <button
                        aria-pressed={webBrowsing}
                        className={`${styles.lightAction} ${webBrowsing ? styles.lightActionActive : ""}`.trim()}
                        disabled={project.default_external_policy !== "allow_external"}
                        onClick={() => setWebBrowsing((value) => !value)}
                        title={
                          project.default_external_policy === "allow_external"
                            ? "为本轮问题联网补充网页资料"
                            : "当前项目未开启联网补充"
                        }
                        type="button"
                      >
                        联网补充
                      </button>

                      <button
                        className={styles.lightAction}
                        disabled={!latestActionableMessage || isStreamingMessage}
                        onClick={() => void handleGenerateReport()}
                        title={latestActionableMessage ? "" : "当前会话还没有可生成报告的结论"}
                        type="button"
                      >
                        生成报告
                      </button>
                    </div>

                    <textarea
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder="继续在这个项目里提问……"
                      rows={2}
                      value={message}
                    />

                    <div className={styles.composerBottom}>
                      <span className={styles.composerHint}>
                        {deepResearch
                          ? "本次发送将走深度调研模式，发送后自动恢复普通提问。"
                          : webBrowsing
                            ? "本次发送会优先查项目资料，并在需要时联网补充网页信息。"
                            : "直接提问即可；需要更完整分析时可手动开启深度调研。"}
                      </span>
                      <button className={styles.sendButton} disabled={!message.trim() || isPending || isStreamingMessage} onClick={() => void handleSendMessage()} type="button">
                        发送
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      {previewSource ? (
        <div className={styles.previewOverlay} onClick={() => setPreviewSource(null)} role="presentation">
          <aside aria-label="来源预览" className={styles.previewSheet} onClick={(event) => event.stopPropagation()}>
            <div className={styles.previewHeader}>
              <div>
                <p className={styles.emptyEyebrow}>来源预览</p>
                <h3>{previewSource.title}</h3>
              </div>
              <button className={styles.lightAction} onClick={() => setPreviewSource(null)} type="button">
                关闭
              </button>
            </div>
            <p className={styles.previewLink}>{previewSource.canonical_uri}</p>
            <div className={styles.previewChunks}>
              {previewSource.preview_chunks.map((chunk) => {
                const context = renderPreviewChunkContext(chunk);
                return (
                  <article key={chunk.id} className={styles.previewChunkCard}>
                    <strong>{chunk.location_label}</strong>
                    {context ? <span className={styles.previewChunkMeta}>{context}</span> : null}
                    <p>{chunk.normalized_text}</p>
                  </article>
                );
              })}
            </div>
            <div className={styles.previewFooter}>
              <Link className={styles.knowledgeLink} href={`/knowledge?projectId=${previewSource.project_id}`}>
                在知识库中管理
              </Link>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

type MessageCardProps = {
  isLatestActionable: boolean;
  isStreamingMessage: boolean;
  message: ChatMessage;
  expanded: boolean;
  onToggleSources: (messageId: string) => void;
  onOpenSource: (sourceId: string) => void;
  onSaveExternalSource: (url: string) => void;
  onSaveSummary: () => void;
  onDeleteCard: (messageId: string) => void;
  sourceIconFor: (item: { source_type: string; canonical_uri: string }) => string | null;
};

function MessageCard({
  isLatestActionable,
  isStreamingMessage,
  message,
  expanded,
  onToggleSources,
  onOpenSource,
  onSaveExternalSource,
  onSaveSummary,
  onDeleteCard,
  sourceIconFor,
}: MessageCardProps) {
  if (message.message_type === "status_card") {
    return (
      <article className={styles.statusCard}>
        <strong>{message.title ?? "状态更新"}</strong>
        <MarkdownMessage content={message.content_md} />
      </article>
    );
  }

  if (message.message_type === "source_update") {
    return (
      <article className={styles.systemCard}>
        <strong>{message.title ?? "资料更新"}</strong>
        <MarkdownMessage content={message.content_md} />
      </article>
    );
  }

  if (message.role === "user") {
    return (
      <div className={styles.userMessageRow}>
        <article className={styles.userMessage}>
          <p>{message.content_md}</p>
        </article>
      </div>
    );
  }

  const isResultCard = message.message_type === "summary_card" || message.message_type === "report_card";

  return (
    <article className={`${styles.assistantMessage} ${isResultCard ? styles.resultCard : ""}`.trim()}>
      {message.title ? <h3>{message.title}</h3> : null}
      <MarkdownMessage content={message.content_md} />
      {message.disclosure_note ? <p className={styles.disclosureNote}>{message.disclosure_note}</p> : null}

      {message.message_type === "assistant_answer" && isLatestActionable ? (
        <div className={styles.messageActions}>
          <button className={styles.lightAction} disabled={isStreamingMessage} onClick={onSaveSummary} type="button">
            保存为摘要
          </button>
        </div>
      ) : null}

      {message.sources.length ? (
        <>
          <button className={styles.sourceBubble} onClick={() => onToggleSources(message.id)} type="button">
            <span className={styles.sourceIcons}>
              {message.sources.slice(0, 3).map((source) => {
                const iconUrl = sourceIconFor(source);
                if (iconUrl) {
                  return <img key={source.id} alt="" className={styles.sourceFavicon} src={iconUrl} />;
                }
                return (
                  <span key={source.id} className={styles.fileTypeIcon}>
                    {source.source_type === "file_pdf" ? "PDF" : "DOCX"}
                  </span>
                );
              })}
            </span>
            <span>{message.sources.length} 个来源</span>
          </button>

          {expanded ? (
            <div className={styles.sourceListInline}>
              {message.sources.map((source) =>
                source.source_kind === "project_source" && source.source_id ? (
                  <button
                    key={source.id}
                    className={styles.sourceTitleButton}
                    onClick={() => onOpenSource(source.source_id!)}
                    type="button"
                  >
                    {source.source_title}
                  </button>
                ) : (
                  <div key={source.id} className={styles.externalSourceCard}>
                    <strong>{source.source_title}</strong>
                    <p>{source.excerpt}</p>
                    <div className={styles.externalSourceActions}>
                      <a href={source.canonical_uri} rel="noreferrer" target="_blank">
                        打开网页
                      </a>
                      <button onClick={() => onSaveExternalSource(source.canonical_uri)} type="button">
                        保存到知识库
                      </button>
                    </div>
                  </div>
                ),
              )}
            </div>
          ) : null}
        </>
      ) : null}

      {isResultCard ? (
        <div className={styles.resultActions}>
          <button
            className={styles.lightAction}
            onClick={() => {
              void navigator.clipboard.writeText(message.content_md);
            }}
            type="button"
          >
            复制
          </button>
          <button className={styles.lightAction} onClick={() => onDeleteCard(message.id)} type="button">
            删除
          </button>
        </div>
      ) : null}
    </article>
  );
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className={styles.markdownBody}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function sortSessions(a: SessionSummary, b: SessionSummary) {
  return (b.latest_message_at ?? b.updated_at).localeCompare(a.latest_message_at ?? a.updated_at);
}

function createTemporaryMessage(input: {
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

function projectInitials(name: string) {
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
