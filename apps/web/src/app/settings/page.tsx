import { AppShell } from "@/components/shell/app-shell";
import { SettingsPageClient } from "@/components/settings/settings-page-client";
import { getModelSettings } from "@/lib/api";

export default async function SettingsPage() {
  const initialSettings = await getModelSettings();

  return (
    <AppShell
      title="模型设置"
      subtitle="在这里统一配置大模型、向量模型和重排模型。保存后，新请求会优先使用这里的全局配置。"
    >
      <SettingsPageClient initialSettings={initialSettings} />
    </AppShell>
  );
}
