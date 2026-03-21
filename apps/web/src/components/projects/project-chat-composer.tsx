"use client";

import Link from "next/link";
import { useRef, type KeyboardEvent } from "react";

import styles from "./project-chat-client.module.css";

type ProjectChatComposerProps = {
  projectId: string;
  sourceCount: number;
  weakSourceMode: boolean;
  canUseWebBrowsing: boolean;
  message: string;
  deepResearch: boolean;
  webBrowsing: boolean;
  showAddSourceMenu: boolean;
  showWebForm: boolean;
  webUrl: string;
  sourceError: string | null;
  sourceNotice: string | null;
  actionError: string | null;
  isStreamingMessage: boolean;
  canGenerateReport: boolean;
  onMessageChange: (value: string) => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onToggleAddSourceMenu: () => void;
  onShowWebForm: () => void;
  onSelectFiles: (files: File[] | null) => void;
  onToggleDeepResearch: () => void;
  onToggleWebBrowsing: () => void;
  onGenerateReport: () => void;
  onSendMessage: () => void;
  onWebUrlChange: (value: string) => void;
  onSubmitWebSource: () => void;
};

export function ProjectChatComposer({
  projectId,
  sourceCount,
  weakSourceMode,
  canUseWebBrowsing,
  message,
  deepResearch,
  webBrowsing,
  showAddSourceMenu,
  showWebForm,
  webUrl,
  sourceError,
  sourceNotice,
  actionError,
  isStreamingMessage,
  canGenerateReport,
  onMessageChange,
  onComposerKeyDown,
  onToggleAddSourceMenu,
  onShowWebForm,
  onSelectFiles,
  onToggleDeepResearch,
  onToggleWebBrowsing,
  onGenerateReport,
  onSendMessage,
  onWebUrlChange,
  onSubmitWebSource,
}: ProjectChatComposerProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputId = `project-chat-file-input-${projectId}`;

  return (
    <div className={styles.composerDock}>
      <div className={styles.composerColumn}>
        <div className={styles.composerMetaRow}>
          <Link className={styles.knowledgeLink} href={`/knowledge?projectId=${projectId}`}>
            知识库 · {sourceCount} 份资料
          </Link>
          {weakSourceMode ? <span className={styles.weakSourceNotice}>当前项目还没有可检索资料，这次对话将以弱资料模式进行。</span> : null}
        </div>

        {showWebForm ? (
          <div className={styles.inlineWebForm}>
            <input onChange={(event) => onWebUrlChange(event.target.value)} placeholder="https://example.com/article" value={webUrl} />
            <button onClick={onSubmitWebSource} type="button">
              添加网页
            </button>
          </div>
        ) : null}

        {sourceError ? <div className={styles.sourceError}>{sourceError}</div> : null}
        {sourceNotice ? <div className={styles.sourceNotice}>{sourceNotice}</div> : null}
        {actionError ? <div className={styles.sourceError}>{actionError}</div> : null}

        <input
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          hidden
          id={fileInputId}
          multiple
          onChange={(event) => {
            const nextFiles = event.currentTarget.files ? Array.from(event.currentTarget.files) : null;
            event.currentTarget.value = "";
            onSelectFiles(nextFiles);
          }}
          ref={fileInputRef}
          type="file"
        />

        <div className={styles.composerSurface}>
          <div className={styles.composerActionRow}>
            <div className={styles.addSourceBox}>
              <button className={styles.lightAction} onClick={onToggleAddSourceMenu} type="button">
                增加资料
              </button>
              {showAddSourceMenu ? (
                <div className={styles.addSourceMenu}>
                  <button onClick={onShowWebForm} type="button">
                    添加网页链接
                  </button>
                  <button
                    onClick={() => {
                      window.setTimeout(() => fileInputRef.current?.click(), 0);
                    }}
                    type="button"
                  >
                    添加文件
                  </button>
                </div>
              ) : null}
            </div>

            <button
              aria-pressed={deepResearch}
              className={`${styles.lightAction} ${deepResearch ? styles.lightActionActive : ""}`.trim()}
              onClick={onToggleDeepResearch}
              type="button"
            >
              深度调研
            </button>

            <button
              aria-pressed={webBrowsing}
              className={`${styles.lightAction} ${webBrowsing ? styles.lightActionActive : ""}`.trim()}
              disabled={!canUseWebBrowsing}
              onClick={onToggleWebBrowsing}
              type="button"
            >
              联网补充
            </button>

            <button className={styles.lightAction} disabled={!canGenerateReport || isStreamingMessage} onClick={onGenerateReport} type="button">
              生成报告
            </button>
          </div>

          <textarea
            onChange={(event) => onMessageChange(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder="围绕当前项目里的资料提问，或继续追问上一个回答。"
            rows={3}
            value={message}
          />

          <div className={styles.composerBottom}>
            <span className={styles.composerHint}>Enter 发送，Shift+Enter 换行</span>
            <button className={styles.sendButton} disabled={isStreamingMessage || !message.trim()} onClick={onSendMessage} type="button">
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
