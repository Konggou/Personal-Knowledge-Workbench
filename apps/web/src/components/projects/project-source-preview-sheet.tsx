"use client";

import Link from "next/link";

import type { SourcePreview } from "@/lib/api";
import { renderPreviewChunkContext } from "@/lib/source-utils";

import styles from "./project-chat-client.module.css";

type ProjectSourcePreviewSheetProps = {
  previewSource: SourcePreview | null;
  onClose: () => void;
};

export function ProjectSourcePreviewSheet({ previewSource, onClose }: ProjectSourcePreviewSheetProps) {
  if (!previewSource) {
    return null;
  }

  return (
    <div className={styles.previewOverlay} onClick={onClose} role="presentation">
      <aside aria-label="来源预览" className={styles.previewSheet} onClick={(event) => event.stopPropagation()}>
        <div className={styles.previewHeader}>
          <div>
            <p className={styles.emptyEyebrow}>来源预览</p>
            <h3>{previewSource.title}</h3>
          </div>
          <div className={styles.previewHeaderActions}>
            <button className={styles.lightAction} onClick={onClose} type="button">
              返回来源列表
            </button>
            <button className={styles.lightAction} onClick={onClose} type="button">
              关闭
            </button>
          </div>
        </div>
        <p className={styles.previewLink}>{previewSource.canonical_uri}</p>
        <div className={styles.previewChunks}>
          {previewSource.preview_chunks.length ? (
            previewSource.preview_chunks.map((chunk) => {
              const context = renderPreviewChunkContext(chunk);
              return (
                <article key={chunk.id} className={styles.previewChunkCard}>
                  <strong>{chunk.location_label}</strong>
                  {context ? <span className={styles.previewChunkMeta}>{context}</span> : null}
                  <p>{chunk.normalized_text}</p>
                </article>
              );
            })
          ) : (
            <article className={styles.previewChunkCard}>
              <strong>暂无预览片段</strong>
              <p>这个来源还没有可展示的片段，可以前往知识库查看完整资料状态。</p>
            </article>
          )}
        </div>
        <div className={styles.previewFooter}>
          <Link className={styles.knowledgeLink} href={`/knowledge?projectId=${previewSource.project_id}`}>
            在知识库中管理
          </Link>
        </div>
      </aside>
    </div>
  );
}
