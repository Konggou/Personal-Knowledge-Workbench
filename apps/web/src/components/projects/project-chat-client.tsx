"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";

import type { KnowledgeSource, ProjectSummary, SessionDetail, SessionSummary, SourcePreview } from "@/lib/api";
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
import { isSupportedFileName, normalizeSourceError } from "@/lib/source-utils";

import { ProjectChatComposer } from "./project-chat-composer";
import { createTemporaryMessage, sortSessions, sourceIconFor } from "./project-chat-helpers";
import { ProjectChatMessageList } from "./project-chat-message-list";
import { ProjectChatSidebar } from "./project-chat-sidebar";
import { ProjectSourcePreviewSheet } from "./project-source-preview-sheet";
import styles from "./project-chat-client.module.css";

type ProjectChatClientProps = {
  project: ProjectSummary;
  allProjects: ProjectSummary[];
  initialProjectSessions: SessionSummary[];
  initialSelectedSession: SessionDetail | null;
  initialSources: KnowledgeSource[];
};

export function ProjectChatClient({
  project,
  allProjects,
  initialProjectSessions,
  initialSelectedSession,
  initialSources,
}: ProjectChatClientProps) {
  const router = useRouter();
  const initialSessionId = initialSelectedSession?.id ?? null;
  const [projects, setProjects] = useState(allProjects);
  const [currentProjectSessions, setCurrentProjectSessions] = useState(initialProjectSessions);
  const [selectedSession, setSelectedSession] = useState(initialSelectedSession);
  const [sources, setSources] = useState(initialSources);
  const [previewSource, setPreviewSource] = useState<SourcePreview | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({ [project.id]: true });
  const [message, setMessage] = useState("");
  const [deepResearch, setDeepResearch] = useState(false);
  const [webBrowsing, setWebBrowsing] = useState(false);
  const [sessionComposerModes, setSessionComposerModes] = useState<
    Record<string, { deepResearch: boolean; webBrowsing: boolean }>
  >(() =>
    initialSessionId
      ? {
          [initialSessionId]: {
            deepResearch: false,
            webBrowsing: false,
          },
        }
      : {},
  );
  const [showAddSourceMenu, setShowAddSourceMenu] = useState(false);
  const [showWebForm, setShowWebForm] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [expandedSourceLists, setExpandedSourceLists] = useState<Record<string, boolean>>({});
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [isStreamingMessage, setIsStreamingMessage] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [sourceNotice, setSourceNotice] = useState<string | null>(null);
  const [savedExternalUris, setSavedExternalUris] = useState<Record<string, boolean>>({});

  const latestActionableMessage = useMemo(() => {
    if (!selectedSession) {
      return null;
    }
    return [...selectedSession.messages]
      .reverse()
      .find((item) => item.message_type === "assistant_answer" && item.supports_report);
  }, [selectedSession]);

  const weakSourceMode = sources.length === 0;
  const canUseWebBrowsing = project.default_external_policy === "allow_external";

  useEffect(() => {
    setBusySessionId(null);
  }, [project.id, selectedSession?.id]);

  useEffect(() => {
    setSourceNotice(null);
    setSavedExternalUris({});
    setPreviewSource(null);
    setExpandedSourceLists({});
  }, [project.id, selectedSession?.id]);

  useEffect(() => {
    if (!selectedSession) {
      setDeepResearch(false);
      setWebBrowsing(false);
      return;
    }

    const remembered = sessionComposerModes[selectedSession.id];
    setDeepResearch(remembered?.deepResearch ?? false);
    setWebBrowsing(remembered?.webBrowsing ?? false);
  }, [selectedSession, sessionComposerModes]);

  const projectTree = useMemo(
    () =>
      projects.map((item) => ({
        ...item,
        sessions: item.id === project.id ? currentProjectSessions : [],
        expanded: expandedProjects[item.id] ?? item.id === project.id,
      })),
    [currentProjectSessions, expandedProjects, project.id, projects],
  );

  function upsertCurrentProjectSessions(nextItems: SessionSummary[]) {
    const sorted = [...nextItems].sort(sortSessions);
    setCurrentProjectSessions(sorted);
    setProjects((previous) =>
      previous.map((item) =>
        item.id === project.id
          ? {
              ...item,
              active_session_count: sorted.length,
              latest_session_id: sorted[0]?.id ?? null,
              latest_session_title: sorted[0]?.title ?? null,
              last_activity_at: sorted[0]?.latest_message_at ?? item.last_activity_at,
            }
          : item,
      ),
    );
  }

  function syncProjectSourceCount(count: number) {
    setProjects((previous) =>
      previous.map((item) =>
        item.id === project.id
          ? {
              ...item,
              active_source_count: count,
            }
          : item,
      ),
    );
  }

  function updateSessionComposerModes(
    sessionId: string,
    next: Partial<{ deepResearch: boolean; webBrowsing: boolean }>,
  ) {
    setSessionComposerModes((previous) => {
      const current = previous[sessionId] ?? { deepResearch: false, webBrowsing: false };
      return {
        ...previous,
        [sessionId]: {
          ...current,
          ...next,
        },
      };
    });
  }

  async function refreshProjectSources() {
    const nextSources = await listProjectSources(project.id);
    setSources(nextSources);
    syncProjectSourceCount(nextSources.length);
    return nextSources;
  }

  async function refreshSelectedSession(sessionId: string) {
    const next = await getSession(sessionId);
    setSelectedSession(next);
    setCurrentProjectSessions((previous) =>
      previous
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
        .sort(sortSessions),
    );
    setProjects((previous) =>
      previous.map((item) =>
        item.id === project.id
          ? {
              ...item,
              latest_session_id: next.id,
              latest_session_title: next.title,
              last_activity_at: next.latest_message_at ?? item.last_activity_at,
            }
          : item,
      ),
    );
    return next;
  }

  async function refreshProjectView(sessionId: string) {
    const [, nextSession] = await Promise.all([refreshProjectSources(), refreshSelectedSession(sessionId)]);
    return nextSession;
  }

  function appendStreamingMessages(userMessage: SessionDetail["messages"][number], assistantMessage: SessionDetail["messages"][number]) {
    setSelectedSession((previous) =>
      previous
        ? {
            ...previous,
            messages: [...previous.messages, userMessage, assistantMessage],
            message_count: previous.message_count + 2,
          }
        : previous,
    );
  }

  function appendStatusMessage(nextMessage: SessionDetail["messages"][number]) {
    setSelectedSession((previous) =>
      previous
        ? {
            ...previous,
            messages: [...previous.messages, nextMessage],
            message_count: previous.message_count + 1,
          }
        : previous,
    );
  }

  function updateMessage(messageId: string, updater: (message: SessionDetail["messages"][number]) => SessionDetail["messages"][number]) {
    setSelectedSession((previous) =>
      previous
        ? {
            ...previous,
            messages: previous.messages.map((item) => (item.id === messageId ? updater(item) : item)),
          }
        : previous,
    );
  }

  function replaceMessage(messageId: string, nextMessage: SessionDetail["messages"][number]) {
    updateMessage(messageId, () => nextMessage);
  }

  async function handleCreateSession() {
    const session = await createSession(project.id);
    upsertCurrentProjectSessions([session, ...currentProjectSessions]);
    updateSessionComposerModes(session.id, { deepResearch: false, webBrowsing: false });
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
    upsertCurrentProjectSessions(currentProjectSessions.map((item) => (item.id === session.id ? { ...item, title: updated.title } : item)));
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
    upsertCurrentProjectSessions(nextSessions);

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
    const useWebBrowsing = webBrowsing && canUseWebBrowsing;

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

    appendStreamingMessages(tempUserMessage, tempAssistantMessage);
    setMessage("");
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
              updateMessage(tempAssistantMessage.id, (item) => ({
                ...item,
                content_md: `${item.content_md}${event.data.delta}`,
              }));
              return;
            }

            if (event.event === "status") {
              appendStatusMessage(event.data.message);
              return;
            }

            if (event.event === "done") {
              replaceMessage(tempAssistantMessage.id, event.data.message);
              return;
            }

            streamFailed = true;
            updateMessage(tempAssistantMessage.id, (item) => ({
              ...item,
              content_md: event.data.message || "生成回复失败，请稍后重试。",
            }));
          },
        },
      );

      if (!streamFailed) {
        await refreshSelectedSession(sessionId);
      }
    } catch (caught) {
      updateMessage(tempAssistantMessage.id, (item) => ({
        ...item,
        content_md: caught instanceof Error ? caught.message : "发送消息失败，请稍后重试。",
      }));
    } finally {
      setIsStreamingMessage(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    void handleSendMessage();
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
    setSourceNotice(null);
    try {
      const savedSource = await createWebSource({
        projectId: project.id,
        url,
        sessionId: selectedSession.id,
      });
      setSavedExternalUris((previous) => ({
        ...previous,
        [url]: true,
        [savedSource.canonical_uri]: true,
      }));
      setSourceNotice("已保存到知识库，可以继续追问新资料。");
      await refreshProjectView(selectedSession.id);
    } catch (caught) {
      setSourceError(caught instanceof Error ? normalizeSourceError(caught.message) : "保存网页资料失败，请稍后重试。");
    }
  }

  async function handleWebSourceCreate() {
    if (!selectedSession || !webUrl.trim()) {
      return;
    }

    setSourceError(null);
    setSourceNotice(null);
    try {
      await createWebSource({
        projectId: project.id,
        url: webUrl.trim(),
        sessionId: selectedSession.id,
      });
      setWebUrl("");
      setShowWebForm(false);
      setShowAddSourceMenu(false);
      setSourceNotice("已添加网页资料。");
      await refreshProjectView(selectedSession.id);
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
    setSourceNotice(null);
    try {
      await createFileSources({
        projectId: project.id,
        files,
        sessionId: selectedSession.id,
      });
      setShowAddSourceMenu(false);
      setSourceNotice("已添加文件资料。");
      await refreshProjectView(selectedSession.id);
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

  return (
    <div className={styles.shell}>
      <div className={`${styles.layout} ${sidebarCollapsed ? styles.layoutCollapsed : ""}`.trim()}>
        <ProjectChatSidebar
          busySessionId={busySessionId}
          onCreateSession={() => void handleCreateSession()}
          onDeleteSession={(sessionId) => void handleDeleteSession(sessionId)}
          onRenameSession={(session) => void handleRenameSession(session)}
          onSelectProject={handleSelectProject}
          onSelectSession={(session) => void handleSelectSession(session)}
          onToggleProject={toggleProject}
          onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
          project={project}
          projectTree={projectTree}
          selectedSession={selectedSession}
          sidebarCollapsed={sidebarCollapsed}
        />

        <section className={styles.chatStage}>
          {!selectedSession ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyContent}>
                <p className={styles.emptyEyebrow}>项目会话</p>
                <h1>{project.name}</h1>
                <p>从项目内新建会话开始提问，或先去知识库补充网页、PDF、DOCX 资料。</p>
                <div className={styles.emptyActions}>
                  <button onClick={() => void handleCreateSession()} type="button">
                    新建会话
                  </button>
                  <a href={`/knowledge?projectId=${project.id}`}>前往知识库</a>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className={styles.chatScroll}>
                <ProjectChatMessageList
                  expandedSourceLists={expandedSourceLists}
                  isStreamingMessage={isStreamingMessage}
                  latestActionableMessageId={latestActionableMessage?.id ?? null}
                  onDeleteCard={(messageId) => void handleDeleteCard(messageId)}
                  onOpenSource={(sourceId) => void openSourcePreview(sourceId)}
                  onSaveExternalSource={(url) => void handleSaveExternalSource(url)}
                  onSaveSummary={() => void handleSaveSummary()}
                  onToggleSources={toggleSourceList}
                  savedExternalUris={savedExternalUris}
                  selectedSession={selectedSession}
                  sourceIconFor={sourceIconFor}
                />
              </div>

              <ProjectChatComposer
                actionError={actionError}
                canGenerateReport={!!latestActionableMessage}
                canUseWebBrowsing={canUseWebBrowsing}
                deepResearch={deepResearch}
                isStreamingMessage={isStreamingMessage}
                message={message}
                onComposerKeyDown={handleComposerKeyDown}
                onGenerateReport={() => void handleGenerateReport()}
                onMessageChange={setMessage}
                onSelectFiles={(files) => {
                  setShowAddSourceMenu(false);
                  void handleFileSourceCreate(files);
                }}
                onSendMessage={() => void handleSendMessage()}
                onShowWebForm={() => {
                  setShowWebForm(true);
                  setShowAddSourceMenu(false);
                }}
                onSubmitWebSource={() => void handleWebSourceCreate()}
                onToggleAddSourceMenu={() => setShowAddSourceMenu((value) => !value)}
                onToggleDeepResearch={() => {
                  if (!selectedSession) {
                    return;
                  }
                  const nextValue = !deepResearch;
                  setDeepResearch(nextValue);
                  updateSessionComposerModes(selectedSession.id, { deepResearch: nextValue });
                }}
                onToggleWebBrowsing={() => {
                  if (!selectedSession) {
                    return;
                  }
                  const nextValue = !webBrowsing;
                  setWebBrowsing(nextValue);
                  updateSessionComposerModes(selectedSession.id, { webBrowsing: nextValue });
                }}
                onWebUrlChange={setWebUrl}
                projectId={project.id}
                showAddSourceMenu={showAddSourceMenu}
                showWebForm={showWebForm}
                sourceCount={sources.length}
                sourceError={sourceError}
                sourceNotice={sourceNotice}
                weakSourceMode={weakSourceMode}
                webBrowsing={webBrowsing}
                webUrl={webUrl}
              />
            </>
          )}
        </section>
      </div>

      <ProjectSourcePreviewSheet onClose={() => setPreviewSource(null)} previewSource={previewSource} />
    </div>
  );
}
