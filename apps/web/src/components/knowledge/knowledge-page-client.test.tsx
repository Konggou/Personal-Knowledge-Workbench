import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { describe, expect, it, vi } from "vitest";

import type { KnowledgeGroup, KnowledgeSource, ProjectSummary } from "@/lib/api";

import { KnowledgePageClient } from "./knowledge-page-client";

const mocks = vi.hoisted(() => ({
  archiveSource: vi.fn(),
  createFileSources: vi.fn(),
  createSession: vi.fn(),
  createWebSource: vi.fn(),
  deleteSource: vi.fn(),
  getSourcePreview: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
  refreshSource: vi.fn(),
  restoreSource: vi.fn(),
  updateWebSource: vi.fn(),
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
    refresh: mocks.refresh,
  }),
}));

vi.mock("@/lib/api", () => ({
  archiveSource: mocks.archiveSource,
  createFileSources: mocks.createFileSources,
  createSession: mocks.createSession,
  createWebSource: mocks.createWebSource,
  deleteSource: mocks.deleteSource,
  getSourcePreview: mocks.getSourcePreview,
  refreshSource: mocks.refreshSource,
  restoreSource: mocks.restoreSource,
  updateWebSource: mocks.updateWebSource,
}));

function createProject(): ProjectSummary {
  return {
    id: "project-1",
    name: "Knowledge Project",
    description: "Project for knowledge page tests",
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

function createSource(overrides: Partial<KnowledgeSource> = {}): KnowledgeSource {
  return {
    id: "source-1",
    project_id: "project-1",
    project_name: "Knowledge Project",
    source_type: "web_page",
    title: "Archived Notes",
    canonical_uri: "https://example.com/archived-notes",
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
    ...overrides,
  };
}

function createGroup(items: KnowledgeSource[]): KnowledgeGroup[] {
  return [
    {
      project_id: "project-1",
      project_name: "Knowledge Project",
      items,
    },
  ];
}

describe("KnowledgePageClient", () => {
  it("includes archived sources in the route when the archived toggle is enabled", () => {
    render(
      <KnowledgePageClient
        includeArchived={false}
        initialGroups={createGroup([createSource()])}
        initialQuery=""
        projects={[createProject()]}
      />,
    );

    fireEvent.click(screen.getByLabelText("显示已归档资料"));
    fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

    expect(mocks.push).toHaveBeenCalledWith("/knowledge?includeArchived=true");
  });

  it("shows the restore action when archived sources are visible", () => {
    render(
      <KnowledgePageClient
        includeArchived
        initialGroups={createGroup([
          createSource({
            id: "source-archived",
            ingestion_status: "archived",
            archived_at: "2026-03-13T00:10:00.000Z",
          }),
        ])}
        initialQuery=""
        projects={[createProject()]}
      />,
    );

    expect(screen.getByLabelText("显示已归档资料")).toBeChecked();
    expect(screen.getByRole("button", { name: "恢复" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "归档" })).not.toBeInTheDocument();
  });

  it("syncs rendered source groups when refreshed props remove an archived item", () => {
    const { rerender } = render(
      <KnowledgePageClient
        includeArchived={false}
        initialGroups={createGroup([createSource()])}
        initialQuery=""
        projects={[createProject()]}
      />,
    );

    expect(screen.getByText("Archived Notes")).toBeInTheDocument();

    rerender(
      <KnowledgePageClient
        includeArchived={false}
        initialGroups={createGroup([])}
        initialQuery=""
        projects={[createProject()]}
      />,
    );

    expect(screen.queryByText("Archived Notes")).not.toBeInTheDocument();
  });
});
