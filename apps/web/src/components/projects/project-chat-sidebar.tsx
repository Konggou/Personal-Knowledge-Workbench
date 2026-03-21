"use client";

import type { ProjectSummary, SessionDetail, SessionSummary } from "@/lib/api";

import { projectInitials } from "./project-chat-helpers";
import styles from "./project-chat-client.module.css";

type ProjectTreeItem = ProjectSummary & {
  sessions: SessionSummary[];
  expanded: boolean;
};

type ProjectChatSidebarProps = {
  project: ProjectSummary;
  projectTree: ProjectTreeItem[];
  selectedSession: SessionDetail | null;
  sidebarCollapsed: boolean;
  busySessionId: string | null;
  onToggleSidebar: () => void;
  onCreateSession: () => void;
  onSelectProject: (projectId: string) => void;
  onToggleProject: (projectId: string) => void;
  onSelectSession: (session: SessionSummary) => void;
  onRenameSession: (session: SessionSummary) => void;
  onDeleteSession: (sessionId: string) => void;
};

export function ProjectChatSidebar({
  project,
  projectTree,
  selectedSession,
  sidebarCollapsed,
  busySessionId,
  onToggleSidebar,
  onCreateSession,
  onSelectProject,
  onToggleProject,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
}: ProjectChatSidebarProps) {
  return (
    <aside className={`${styles.sidebar} ${sidebarCollapsed ? styles.sidebarCollapsed : ""}`.trim()}>
      <div className={styles.sidebarTop}>
        <button
          aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          className={styles.collapseButton}
          onClick={onToggleSidebar}
          title={sidebarCollapsed ? "展开" : "收起"}
          type="button"
        >
          <span aria-hidden="true" className={styles.collapseGlyph}>
            {sidebarCollapsed ? ">" : "<"}
          </span>
        </button>
        {!sidebarCollapsed ? (
          <button className={styles.newSessionButton} onClick={onCreateSession} type="button">
            新建会话
          </button>
        ) : (
          <button aria-label="新建会话" className={styles.railActionButton} onClick={onCreateSession} type="button">
            +
          </button>
        )}
      </div>

      {sidebarCollapsed ? (
        <div className={styles.railProjectList}>
          {projectTree.map((item) => (
            <button
              key={item.id}
              aria-label={item.name}
              className={`${styles.railProjectButton} ${item.id === project.id ? styles.railProjectButtonActive : ""}`.trim()}
              onClick={() => onSelectProject(item.id)}
              title={item.name}
              type="button"
            >
              {projectInitials(item.name)}
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.projectTree}>
          {projectTree.map((item) => (
            <section key={item.id} className={`${styles.projectSection} ${item.id === project.id ? styles.projectSectionActive : ""}`.trim()}>
              <div className={styles.projectRow}>
                <button className={styles.projectButton} onClick={() => onSelectProject(item.id)} type="button">
                  <span className={styles.projectBadge}>{projectInitials(item.name)}</span>
                  <span className={styles.projectMeta}>
                    <strong>{item.name}</strong>
                    <span>
                      {item.active_source_count} 份资料 · {item.active_session_count} 个会话
                    </span>
                  </span>
                </button>
                <button
                  aria-label={item.expanded ? `收起 ${item.name}` : `展开 ${item.name}`}
                  className={styles.projectToggleButton}
                  onClick={() => onToggleProject(item.id)}
                  type="button"
                >
                  {item.expanded ? "-" : "+"}
                </button>
              </div>

              {item.expanded ? (
                <div className={styles.sessionList}>
                  {item.sessions.length ? (
                    item.sessions.map((session) => (
                      <article
                        key={session.id}
                        className={`${styles.sessionItem} ${selectedSession?.id === session.id ? styles.sessionItemActive : ""}`.trim()}
                      >
                        <button
                          className={styles.sessionSelect}
                          disabled={busySessionId === session.id}
                          onClick={() => onSelectSession(session)}
                          type="button"
                        >
                          <strong>{session.title}</strong>
                          <span>{session.message_count} 条消息</span>
                        </button>
                        {item.id === project.id ? (
                          <div className={styles.sessionItemActions}>
                            <button onClick={() => onRenameSession(session)} type="button">
                              重命名
                            </button>
                            <button onClick={() => onDeleteSession(session.id)} type="button">
                              删除
                            </button>
                          </div>
                        ) : null}
                      </article>
                    ))
                  ) : (
                    <div className={styles.sidebarEmpty}>这个项目还没有会话。</div>
                  )}
                </div>
              ) : null}
            </section>
          ))}
        </div>
      )}
    </aside>
  );
}
