"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "@/lib/api";

import { formatSourceHost, summarizeSourceKinds } from "./project-chat-helpers";
import styles from "./project-chat-client.module.css";

type ProjectChatMessageCardProps = {
  isLatestActionable: boolean;
  isStreamingMessage: boolean;
  message: ChatMessage;
  expanded: boolean;
  onToggleSources: (messageId: string) => void;
  onOpenSource: (sourceId: string) => void;
  onSaveExternalSource: (url: string) => void;
  onSaveSummary: () => void;
  onDeleteCard: (messageId: string) => void;
  savedExternalUris: Record<string, boolean>;
  sourceIconFor: (item: { source_type: string; canonical_uri: string }) => string | null;
};

export function ProjectChatMessageCard({
  isLatestActionable,
  isStreamingMessage,
  message,
  expanded,
  onToggleSources,
  onOpenSource,
  onSaveExternalSource,
  onSaveSummary,
  onDeleteCard,
  savedExternalUris,
  sourceIconFor,
}: ProjectChatMessageCardProps) {
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
  const sourceSummary = summarizeSourceKinds(message.sources);

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
            <span>{sourceSummary}</span>
          </button>

          {expanded ? (
            <div className={styles.sourceListInline}>
              {message.sources.map((source) =>
                source.source_kind === "project_source" && source.source_id ? (
                  <div key={source.id} className={styles.sourceListItem}>
                    <div className={styles.sourceMetaLine}>
                      <span className={`${styles.sourceKindTag} ${styles.sourceKindProject}`.trim()}>项目资料</span>
                      <span className={styles.sourceCanonical}>{source.location_label}</span>
                    </div>
                    <button className={styles.sourceTitleButton} onClick={() => onOpenSource(source.source_id!)} type="button">
                      {source.source_title}
                    </button>
                  </div>
                ) : (
                  <div key={source.id} className={styles.externalSourceCard}>
                    <div className={styles.sourceMetaLine}>
                      <span className={`${styles.sourceKindTag} ${styles.sourceKindWeb}`.trim()}>网页补充</span>
                      <span className={styles.sourceCanonical}>{formatSourceHost(source.canonical_uri)}</span>
                    </div>
                    <strong>{source.source_title}</strong>
                    <p>{source.excerpt}</p>
                    <div className={styles.externalSourceActions}>
                      <a href={source.canonical_uri} rel="noreferrer" target="_blank">
                        打开网页
                      </a>
                      <button
                        disabled={!!savedExternalUris[source.canonical_uri]}
                        onClick={() => onSaveExternalSource(source.canonical_uri)}
                        type="button"
                      >
                        {savedExternalUris[source.canonical_uri] ? "已保存到知识库" : "保存到知识库"}
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
