import { AppShell } from "@/components/shell/app-shell";
import { SessionsPageClient } from "@/components/sessions/sessions-page-client";
import { listSessionGroups } from "@/lib/api";

export default async function SessionsPage() {
  const groups = await listSessionGroups();

  return (
    <AppShell subtitle="全局会话按项目分组。这里负责浏览并回到某条对话，不负责管理知识库。" title="最近会话">
      <SessionsPageClient initialGroups={groups} />
    </AppShell>
  );
}
