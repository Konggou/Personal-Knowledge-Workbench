"use client";

import { useState } from "react";

import type { ModelSettings } from "@/lib/api";
import { updateModelSettings } from "@/lib/api";

import styles from "./settings-page-client.module.css";

type SettingsPageClientProps = {
  initialSettings: ModelSettings;
};

export function SettingsPageClient({ initialSettings }: SettingsPageClientProps) {
  const [llmBaseUrl, setLlmBaseUrl] = useState(initialSettings.llm.base_url);
  const [llmModel, setLlmModel] = useState(initialSettings.llm.model);
  const [llmTimeout, setLlmTimeout] = useState(String(initialSettings.llm.timeout_seconds));
  const [llmApiKey, setLlmApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);

  const [embeddingModel, setEmbeddingModel] = useState(initialSettings.embedding.model_name);
  const [embeddingDimension, setEmbeddingDimension] = useState(String(initialSettings.embedding.dimension));
  const [embeddingAllowDownloads, setEmbeddingAllowDownloads] = useState(initialSettings.embedding.allow_downloads);

  const [rerankerBackend, setRerankerBackend] = useState(initialSettings.reranker.backend);
  const [rerankerModel, setRerankerModel] = useState(initialSettings.reranker.model_name);
  const [rerankerRemoteUrl, setRerankerRemoteUrl] = useState(initialSettings.reranker.remote_url);
  const [rerankerRemoteTimeout, setRerankerRemoteTimeout] = useState(String(initialSettings.reranker.remote_timeout_seconds));
  const [rerankerTopN, setRerankerTopN] = useState(String(initialSettings.reranker.top_n));
  const [rerankerAllowDownloads, setRerankerAllowDownloads] = useState(initialSettings.reranker.allow_downloads);

  const [savedSettings, setSavedSettings] = useState(initialSettings);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      const next = await updateModelSettings({
        llm: {
          base_url: llmBaseUrl.trim(),
          model: llmModel.trim(),
          timeout_seconds: Number(llmTimeout),
          api_key: clearApiKey ? null : llmApiKey.trim() || null,
          clear_api_key: clearApiKey,
        },
        embedding: {
          model_name: embeddingModel.trim(),
          dimension: Number(embeddingDimension),
          allow_downloads: embeddingAllowDownloads,
        },
        reranker: {
          backend: rerankerBackend,
          model_name: rerankerModel.trim(),
          remote_url: rerankerRemoteUrl.trim(),
          remote_timeout_seconds: Number(rerankerRemoteTimeout),
          top_n: Number(rerankerTopN),
          allow_downloads: rerankerAllowDownloads,
        },
      });
      setSavedSettings(next);
      setLlmApiKey("");
      setClearApiKey(false);
      setNotice("模型设置已保存，新请求会使用最新配置。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "保存模型设置失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className={styles.layout}>
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>大模型</h2>
          <p className={styles.sectionBody}>用于普通对话、grounded 回答与深度调研生成。</p>
        </div>
        <div className={styles.grid}>
          <label className={styles.field}>
            <span>Base URL</span>
            <input onChange={(event) => setLlmBaseUrl(event.target.value)} value={llmBaseUrl} />
          </label>
          <label className={styles.field}>
            <span>Model</span>
            <input onChange={(event) => setLlmModel(event.target.value)} value={llmModel} />
          </label>
          <label className={styles.field}>
            <span>Timeout (seconds)</span>
            <input onChange={(event) => setLlmTimeout(event.target.value)} type="number" value={llmTimeout} />
          </label>
          <label className={styles.field}>
            <span>API Key</span>
            <input
              onChange={(event) => setLlmApiKey(event.target.value)}
              placeholder="留空表示不修改"
              type="password"
              value={llmApiKey}
            />
            <span className={styles.fieldHint}>
              {savedSettings.llm.has_api_key
                ? `已配置：${savedSettings.llm.api_key_preview ?? "******"}`
                : "当前未配置 API Key"}
            </span>
          </label>
        </div>
        <label className={styles.checkboxRow}>
          <input checked={clearApiKey} onChange={(event) => setClearApiKey(event.target.checked)} type="checkbox" />
          <span>清空当前 API Key</span>
        </label>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>向量模型</h2>
          <p className={styles.sectionBody}>用于资料入库、语义检索和向量化查询。</p>
        </div>
        <div className={styles.grid}>
          <label className={styles.field}>
            <span>Model Name</span>
            <input onChange={(event) => setEmbeddingModel(event.target.value)} value={embeddingModel} />
          </label>
          <label className={styles.field}>
            <span>Dimension</span>
            <input onChange={(event) => setEmbeddingDimension(event.target.value)} type="number" value={embeddingDimension} />
          </label>
        </div>
        <label className={styles.checkboxRow}>
          <input
            checked={embeddingAllowDownloads}
            onChange={(event) => setEmbeddingAllowDownloads(event.target.checked)}
            type="checkbox"
          />
          <span>允许自动下载向量模型</span>
        </label>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>重排模型</h2>
          <p className={styles.sectionBody}>用于最终证据排序与候选结果重排。</p>
        </div>
        <div className={styles.grid}>
          <label className={styles.field}>
            <span>Backend</span>
            <select onChange={(event) => setRerankerBackend(event.target.value as typeof rerankerBackend)} value={rerankerBackend}>
              <option value="rule">rule</option>
              <option value="cross_encoder_local">cross_encoder_local</option>
              <option value="cross_encoder_remote">cross_encoder_remote</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Model Name</span>
            <input onChange={(event) => setRerankerModel(event.target.value)} value={rerankerModel} />
          </label>
          <label className={styles.field}>
            <span>Remote URL</span>
            <input onChange={(event) => setRerankerRemoteUrl(event.target.value)} value={rerankerRemoteUrl} />
          </label>
          <label className={styles.field}>
            <span>Remote Timeout (seconds)</span>
            <input
              onChange={(event) => setRerankerRemoteTimeout(event.target.value)}
              type="number"
              value={rerankerRemoteTimeout}
            />
          </label>
          <label className={styles.field}>
            <span>Top N</span>
            <input onChange={(event) => setRerankerTopN(event.target.value)} type="number" value={rerankerTopN} />
          </label>
        </div>
        <label className={styles.checkboxRow}>
          <input
            checked={rerankerAllowDownloads}
            onChange={(event) => setRerankerAllowDownloads(event.target.checked)}
            type="checkbox"
          />
          <span>允许自动下载重排模型</span>
        </label>
      </section>

      <div className={styles.actions}>
        <button className={styles.saveButton} disabled={isSaving} onClick={() => void handleSave()} type="button">
          {isSaving ? "保存中..." : "保存设置"}
        </button>
        {notice ? <span className={styles.success}>{notice}</span> : null}
        {error ? <span className={styles.error}>{error}</span> : null}
      </div>
      <p className={styles.meta}>当前页面保存的是全局模型配置，不区分项目。</p>
    </div>
  );
}
