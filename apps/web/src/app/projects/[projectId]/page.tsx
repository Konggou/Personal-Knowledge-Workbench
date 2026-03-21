import { AppShell } from "@/components/shell/app-shell";
import { ProjectChatClient } from "@/components/projects/project-chat-client";
import { getProject, getSession, listProjectSessions, listProjects, listProjectSources } from "@/lib/api";

import styles from "@/components/projects/project-chat-client.module.css";

type ProjectPageProps = {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ sessionId?: string }>;
};

export default async function ProjectPage({ params, searchParams }: ProjectPageProps) {
  const [{ projectId }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const sessionId = resolvedSearchParams.sessionId?.trim();
  const selectedSessionPromise = sessionId
    ? getSession(sessionId).catch(() => null)
    : Promise.resolve(null);

  const [project, projects, projectSessions, sources, selectedSession] = await Promise.all([
    getProject(projectId),
    listProjects(),
    listProjectSessions(projectId),
    listProjectSources(projectId),
    selectedSessionPromise,
  ]);

  const normalizedSelectedSession = selectedSession?.project_id === projectId ? selectedSession : null;
  return (
    <AppShell headerClassName={styles.appShellHeader} mainClassName={styles.appShellMain}>
      <ProjectChatClient
        allProjects={projects}
        initialProjectSessions={projectSessions}
        initialSelectedSession={normalizedSelectedSession}
        initialSources={sources}
        project={project}
      />
    </AppShell>
  );
}
