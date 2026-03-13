"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { SessionGroup } from "@/lib/api";
import { deleteSession, renameSession } from "@/lib/api";

import styles from "./sessions-page-client.module.css";

type SessionsPageClientProps = {
  initialGroups: SessionGroup[];
};

export function SessionsPageClient({ initialGroups }: SessionsPageClientProps) {
  const router = useRouter();
  const [groups, setGroups] = useState(initialGroups);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);

  async function handleRename(sessionId: string, currentTitle: string) {
    const title = window.prompt("新的会话名称", currentTitle)?.trim();
    if (!title) {
      return;
    }
    setBusySessionId(sessionId);
    try {
      const updated = await renameSession(sessionId, title);
      setGroups((previous) =>
        previous.map((group) => ({
          ...group,
          items: group.items.map((item) => (item.id === sessionId ? { ...item, title: updated.title } : item)),
        })),
      );
    } finally {
      setBusySessionId(null);
    }
  }

  async function handleDelete(sessionId: string) {
    if (!window.confirm("确认删除这条会话吗？")) {
      return;
    }
    setBusySessionId(sessionId);
    try {
      await deleteSession(sessionId);
      setGroups((previous) =>
        previous
          .map((group) => ({
            ...group,
            items: group.items.filter((item) => item.id !== sessionId),
          }))
          .filter((group) => group.items.length > 0),
      );
      router.refresh();
    } finally {
      setBusySessionId(null);
    }
  }

  return (
    <div className={styles.layout}>
      {groups.map((group) => (
        <section key={group.project_id} className={styles.groupCard}>
          <div className={styles.groupHeader}>
            <div>
              <h2 className={styles.groupTitle}>{group.project_name}</h2>
              <p className={styles.groupMeta}>{group.items.length} 个会话</p>
            </div>
            <Link className={styles.groupLink} href={`/projects/${group.project_id}`}>
              进入项目
            </Link>
          </div>

          <div className={styles.sessionList}>
            {group.items.map((item) => (
              <article key={item.id} className={styles.sessionCard}>
                <Link className={styles.sessionLink} href={`/projects/${item.project_id}?sessionId=${item.id}`}>
                  <strong>{item.title}</strong>
                  <span>{item.message_count} 条消息</span>
                </Link>
                <div className={styles.actions}>
                  <button disabled={busySessionId === item.id} onClick={() => handleRename(item.id, item.title)} type="button">
                    重命名
                  </button>
                  <button disabled={busySessionId === item.id} onClick={() => handleDelete(item.id)} type="button">
                    删除
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}

      {!groups.length ? <div className={styles.emptyState}>当前还没有任何会话。先去工作台创建项目，再进入项目里新建会话。</div> : null}
    </div>
  );
}
