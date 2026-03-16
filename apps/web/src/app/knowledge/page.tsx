import { AppShell } from "@/components/shell/app-shell";
import { KnowledgePageClient } from "@/components/knowledge/knowledge-page-client";
import { listKnowledge, listProjects } from "@/lib/api";

type KnowledgePageProps = {
  searchParams: Promise<{
    query?: string;
    projectId?: string;
    includeArchived?: string;
  }>;
};

export default async function KnowledgePage({ searchParams }: KnowledgePageProps) {
  const resolved = await searchParams;
  const query = resolved.query?.trim() ?? "";
  const projectId = resolved.projectId?.trim() || undefined;
  const includeArchived = resolved.includeArchived === "true";

  const [groups, projects] = await Promise.all([
    listKnowledge({ query, projectId, includeArchived }),
    listProjects({ includeArchived: false }),
  ]);

  return (
    <AppShell subtitle="知识库按项目分组，先预览来源，再决定是否进入聊天。全局搜索也收敛在这里。" title="管理你的资料与来源">
      <KnowledgePageClient
        includeArchived={includeArchived}
        initialGroups={groups}
        initialProjectId={projectId}
        initialQuery={query}
        projects={projects}
      />
    </AppShell>
  );
}
