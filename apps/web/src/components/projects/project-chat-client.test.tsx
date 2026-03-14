import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage, KnowledgeSource, ProjectSummary, SessionDetail, SessionGroup, SessionSummary } from "@/lib/api";

import { ProjectChatClient } from "./project-chat-client";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  createFileSources: vi.fn(),
  createReportCard: vi.fn(),
  createSession: vi.fn(),
  createSummaryCard: vi.fn(),
  createWebSource: vi.fn(),
  deleteMessageCard: vi.fn(),
  deleteSession: vi.fn(),
  getSession: vi.fn(),
  getSourcePreview: vi.fn(),
  listProjectSources: vi.fn(),
  renameSession: vi.fn(),
  streamSessionMessage: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mocks.push,
  }),
}));

vi.mock("@/lib/api", () => ({
  createFileSources: mocks.createFileSources,
  createReportCard: mocks.createReportCard,
  createSession: mocks.createSession,
  createSummaryCard: mocks.createSummaryCard,
  createWebSource: mocks.createWebSource,
  deleteMessageCard: mocks.deleteMessageCard,
  deleteSession: mocks.deleteSession,
  getSession: mocks.getSession,
  getSourcePreview: mocks.getSourcePreview,
  listProjectSources: mocks.listProjectSources,
  renameSession: mocks.renameSession,
  streamSessionMessage: mocks.streamSessionMessage,
}));

function createProject(): ProjectSummary {
  return {
    id: "project-1",
    name: "Grounded Project",
    description: "Project for grounded chat tests",
    default_external_policy: "allow_external",
    status: "active",
    current_snapshot_id: null,
    last_activity_at: "2026-03-13T00:00:00.000Z",
    created_at: "2026-03-13T00:00:00.000Z",
    updated_at: "2026-03-13T00:00:00.000Z",
    archived_at: null,
    active_session_count: 1,
    active_source_count: 1,
    latest_session_id: "session-1",
    latest_session_title: "新会话",
  };
}

function createSessionSummary(): SessionSummary {
  return {
    id: "session-1",
    project_id: "project-1",
    project_name: "Grounded Project",
    title: "新会话",
    title_source: "pending",
    status: "active",
    latest_message_at: "2026-03-13T00:00:00.000Z",
    created_at: "2026-03-13T00:00:00.000Z",
    updated_at: "2026-03-13T00:00:00.000Z",
    deleted_at: null,
    message_count: 0,
  };
}

function createKnowledgeSource(): KnowledgeSource {
  return {
    id: "source-1",
    project_id: "project-1",
    project_name: "Grounded Project",
    source_type: "web_page",
    title: "Quest 3 Notes",
    canonical_uri: "https://example.com/quest-3",
    original_filename: null,
    mime_type: null,
    ingestion_status: "ready",
    quality_level: "normal",
    refresh_strategy: "manual",
    last_refreshed_at: null,
    error_code: null,
    error_message: null,
    created_at: "2026-03-13T00:00:00.000Z",
    updated_at: "2026-03-13T00:00:00.000Z",
    archived_at: null,
    deleted_at: null,
    favicon_url: null,
  };
}

function createUserMessage(content: string): ChatMessage {
  return {
    id: "user-1",
    session_id: "session-1",
    project_id: "project-1",
    seq_no: 1,
    role: "user",
    message_type: "user_prompt",
    title: null,
    content_md: content,
    source_mode: null,
    evidence_status: null,
    disclosure_note: null,
    status_label: null,
    supports_summary: false,
    supports_report: false,
    related_message_id: null,
    created_at: "2026-03-13T00:00:00.000Z",
    updated_at: "2026-03-13T00:00:00.000Z",
    deleted_at: null,
    sources: [],
  };
}

function createAssistantMessage(): ChatMessage {
  return {
    id: "assistant-final",
    session_id: "session-1",
    project_id: "project-1",
    seq_no: 2,
    role: "assistant",
    message_type: "assistant_answer",
    title: null,
    content_md: "Quest 3 默认配套的是 **Touch Plus** 手柄。",
    source_mode: "project_grounded",
    evidence_status: "grounded",
    disclosure_note: "补充说明：部分补充说明来自通用常识，不来自当前项目资料。",
    status_label: null,
    supports_summary: true,
    supports_report: true,
    related_message_id: null,
    created_at: "2026-03-13T00:00:00.000Z",
    updated_at: "2026-03-13T00:00:00.000Z",
    deleted_at: null,
    sources: [
      {
        id: "message-source-1",
        source_id: "source-1",
        source_kind: "project_source",
        chunk_id: null,
        source_rank: 1,
        source_type: "web_page",
        source_title: "Quest 3 Notes",
        canonical_uri: "https://example.com/quest-3",
        external_uri: null,
        location_label: "Projects #1",
        excerpt: "Quest 3 ships with Touch Plus controllers by default.",
        relevance_score: 4.2,
      },
    ],
  };
}

function createSummaryCardMessage(): ChatMessage {
  return {
    id: "summary-1",
    session_id: "session-1",
    project_id: "project-1",
    seq_no: 3,
    role: "assistant",
    message_type: "summary_card",
    title: "摘要：基于当前资料的回答",
    content_md: "这是摘要卡内容。",
    source_mode: null,
    evidence_status: null,
    disclosure_note: null,
    status_label: null,
    supports_summary: false,
    supports_report: false,
    related_message_id: "assistant-final",
    created_at: "2026-03-13T00:02:00.000Z",
    updated_at: "2026-03-13T00:02:00.000Z",
    deleted_at: null,
    sources: [],
  };
}

function createInitialSessionDetail(): SessionDetail {
  return {
    ...createSessionSummary(),
    messages: [],
  };
}

function createSessionWithAssistantAnswer(): SessionDetail {
  return {
    ...createSessionSummary(),
    message_count: 2,
    messages: [createUserMessage("我用的是哪个手柄？"), createAssistantMessage()],
  };
}

function createSessionGroups(): SessionGroup[] {
  return [
    {
      project_id: "project-1",
      project_name: "Grounded Project",
      items: [createSessionSummary()],
    },
  ];
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

function deferredValue<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProjectChatClient", () => {
  it("streams grounded content into the placeholder and only mounts sources on done", async () => {
    const gate = deferred();
    const project = createProject();
    const initialSession = createInitialSessionDetail();
    const finalAssistant = createAssistantMessage();
    const finalSession = {
      ...initialSession,
      title_source: "auto" as const,
      message_count: 2,
      latest_message_at: "2026-03-13T00:01:00.000Z",
      messages: [createUserMessage("我用的是哪个手柄？"), finalAssistant],
    };

    mocks.streamSessionMessage.mockImplementationOnce(async (_input: unknown, handlers: { onEvent: (event: any) => void }) => {
      handlers.onEvent({
        event: "delta",
        data: { delta: "Quest 3 默认配套的是 " },
      });
      await gate.promise;
      handlers.onEvent({
        event: "done",
        data: { message: finalAssistant },
      });
    });
    mocks.getSession.mockResolvedValueOnce(finalSession);

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={initialSession}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "我用的是哪个手柄？" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(mocks.streamSessionMessage).toHaveBeenCalled());
    expect(mocks.streamSessionMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        deepResearch: false,
        webBrowsing: false,
      }),
      expect.any(Object),
    );
    expect(screen.getByText("我用的是哪个手柄？")).toBeInTheDocument();
    expect(screen.getByText("Quest 3 默认配套的是")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /来源/ })).not.toBeInTheDocument();
    expect(screen.queryByText("补充说明：部分补充说明来自通用常识，不来自当前项目资料。")).not.toBeInTheDocument();

    gate.resolve();

    await waitFor(() => expect(screen.getByRole("button", { name: /项目来源/ })).toBeInTheDocument());
    expect(screen.getByText("补充说明：部分补充说明来自通用常识，不来自当前项目资料。")).toBeInTheDocument();
  });

  it("sends the web browsing flag when the toggle is enabled", async () => {
    const project = createProject();
    const session = createInitialSessionDetail();
    const finalAssistant = createAssistantMessage();
    const refreshedSession = {
      ...session,
      title_source: "auto" as const,
      message_count: 2,
      latest_message_at: "2026-03-13T00:01:00.000Z",
      messages: [createUserMessage("请联网补充一下"), finalAssistant],
    };

    mocks.streamSessionMessage.mockImplementationOnce(async (_input: unknown, handlers: { onEvent: (event: any) => void }) => {
      handlers.onEvent({ event: "done", data: { message: finalAssistant } });
    });
    mocks.getSession.mockResolvedValueOnce(refreshedSession);

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={session}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "联网补充" }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "请联网补充一下" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(mocks.streamSessionMessage).toHaveBeenCalled());
    expect(mocks.streamSessionMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        deepResearch: false,
        webBrowsing: true,
      }),
      expect.any(Object),
    );
  });

  it("renders a summary card after saving the latest actionable answer", async () => {
    const project = createProject();
    const initialSession = createSessionWithAssistantAnswer();
    const summaryCard = createSummaryCardMessage();
    const nextSession = {
      ...initialSession,
      message_count: 3,
      messages: [...initialSession.messages, summaryCard],
    };

    mocks.createSummaryCard.mockResolvedValueOnce(nextSession);

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={initialSession}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "保存为摘要" }));

    await waitFor(() => expect(mocks.createSummaryCard).toHaveBeenCalledWith("session-1"));
    expect(await screen.findByRole("heading", { name: "摘要：基于当前资料的回答" })).toBeInTheDocument();
    expect(screen.getByText("这是摘要卡内容。")).toBeInTheDocument();
  });

  it("keeps summary and report actions disabled until stream refresh completes", async () => {
    const gate = deferred();
    const refreshGate = deferredValue<SessionDetail>();
    const project = createProject();
    const initialSession = createInitialSessionDetail();
    const finalAssistant = createAssistantMessage();
    const finalSession = {
      ...initialSession,
      title_source: "auto" as const,
      message_count: 2,
      latest_message_at: "2026-03-13T00:01:00.000Z",
      messages: [createUserMessage("我用的是哪个手柄？"), finalAssistant],
    };

    mocks.streamSessionMessage.mockImplementationOnce(async (_input: unknown, handlers: { onEvent: (event: any) => void }) => {
      handlers.onEvent({
        event: "delta",
        data: { delta: "Quest 3 默认配套的是 " },
      });
      await gate.promise;
      handlers.onEvent({
        event: "done",
        data: { message: finalAssistant },
      });
    });
    mocks.getSession.mockImplementationOnce(() => refreshGate.promise);

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={initialSession}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "我用的是哪个手柄？" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(mocks.streamSessionMessage).toHaveBeenCalled());
    gate.resolve();

    const summaryButton = await screen.findByRole("button", { name: "保存为摘要" });
    const reportButton = screen.getByRole("button", { name: "生成报告" });
    expect(summaryButton).toBeDisabled();
    expect(reportButton).toBeDisabled();

    refreshGate.resolve(finalSession);

    await waitFor(() => expect(screen.getByRole("button", { name: "保存为摘要" })).toBeEnabled());
    expect(screen.getByRole("button", { name: "生成报告" })).toBeEnabled();
  });

  it("updates the sidebar source count after adding a file source", async () => {
    const project = createProject();
    const initialSession = createInitialSessionDetail();
    const nextSources = [
      createKnowledgeSource(),
      {
        ...createKnowledgeSource(),
        id: "source-2",
        title: "开题报告.docx",
        source_type: "file_docx" as const,
        canonical_uri: "file:///outline.docx",
        original_filename: "开题报告.docx",
      },
    ];

    mocks.createFileSources.mockResolvedValueOnce(undefined);
    mocks.listProjectSources.mockResolvedValueOnce(nextSources);
    mocks.getSession.mockResolvedValueOnce(initialSession);

    const { container } = render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={initialSession}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();

    fireEvent.change(fileInput!, {
      target: {
        files: [new File(["dummy"], "开题报告.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      },
    });

    await waitFor(() => expect(mocks.createFileSources).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole("link", { name: /知识库 · 2 份资料/ })).toBeInTheDocument());
    expect(screen.getByText(/2 份资料 · 1 个会话/)).toBeInTheDocument();
  });

  it("renders structured preview context when opening a source from the source bubble", async () => {
    const project = createProject();
    const session = createSessionWithAssistantAnswer();

    mocks.getSourcePreview.mockResolvedValueOnce({
      ...createKnowledgeSource(),
      preview_chunks: [
        {
          id: "chunk-1",
          location_label: "研究内容 #1",
          section_type: "body",
          heading_path: "研究内容",
          field_label: "课题名称",
          table_origin: "table_row_1",
          proposition_type: "method",
          excerpt: "系统需要覆盖空气质量采集。",
          normalized_text: "系统需要覆盖空气质量采集。",
          char_count: 13,
        },
      ],
    });

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={session}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /项目来源/ }));
    fireEvent.click(screen.getByRole("button", { name: "Quest 3 Notes" }));

    await waitFor(() => expect(mocks.getSourcePreview).toHaveBeenCalledWith("source-1"));
    expect(screen.getByText("项目资料")).toBeInTheDocument();
    expect(await screen.findByText("研究内容 · 课题名称")).toBeInTheDocument();
    expect(screen.getByText("系统需要覆盖空气质量采集。")).toBeInTheDocument();
  });

  it("allows saving an external web source from the source bubble", async () => {
    const project = createProject();
    const externalAnswer: ChatMessage = {
      ...createAssistantMessage(),
      id: "assistant-external",
      sources: [
        {
          id: "message-source-external",
          source_id: null,
          source_kind: "external_web",
          chunk_id: null,
          source_rank: 1,
          source_type: "web_page",
          source_title: "External Research Note",
          canonical_uri: "https://example.com/external-note",
          external_uri: "https://example.com/external-note",
          location_label: "网页补充 #1",
          excerpt: "External benchmark notes from the web.",
          relevance_score: 3.8,
        },
      ],
    };
    const session: SessionDetail = {
      ...createSessionSummary(),
      message_count: 2,
      messages: [createUserMessage("请联网补充说明"), externalAnswer],
    };
    mocks.createWebSource.mockResolvedValueOnce(createKnowledgeSource());
    mocks.listProjectSources.mockResolvedValueOnce([createKnowledgeSource()]);
    mocks.getSession.mockResolvedValueOnce(session);

    render(
      <ProjectChatClient
        allProjects={[project]}
        initialSelectedSession={session}
        initialSessionGroups={createSessionGroups()}
        initialSources={[createKnowledgeSource()]}
        project={project}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /网页来源/ }));
    expect(screen.getByText("网页补充")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存到知识库" }));

    await waitFor(() =>
      expect(mocks.createWebSource).toHaveBeenCalledWith(
        expect.objectContaining({
          url: "https://example.com/external-note",
        }),
      ),
    );
    expect(await screen.findByText("已保存到知识库，可继续追问新资料。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已保存到知识库" })).toBeDisabled();
  });
});
