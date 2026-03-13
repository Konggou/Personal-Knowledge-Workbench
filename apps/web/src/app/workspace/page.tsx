import { AppShell } from "@/components/shell/app-shell";
import { WorkspacePageClient } from "@/components/workspace/workspace-page-client";
import { listProjects } from "@/lib/api";

type WorkspacePageProps = {
  searchParams: Promise<{
    query?: string;
    includeArchived?: string;
  }>;
};

export default async function WorkspacePage({ searchParams }: WorkspacePageProps) {
  const resolved = await searchParams;
  const query = resolved.query?.trim() ?? "";
  const includeArchived = resolved.includeArchived === "true";
  const projects = await listProjects({ query, includeArchived });

  return (
    <AppShell subtitle="工作台按项目聚合最近活跃的知识库入口。进入项目后，再用会话继续处理具体问题。" title="回到正在工作的项目">
      <WorkspacePageClient includeArchived={includeArchived} initialProjects={projects} initialQuery={query} />
    </AppShell>
  );
}
