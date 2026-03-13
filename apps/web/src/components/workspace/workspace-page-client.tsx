"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import type { ProjectSummary } from "@/lib/api";
import { createProject } from "@/lib/api";

import styles from "./workspace-page-client.module.css";

type WorkspacePageClientProps = {
  initialProjects: ProjectSummary[];
  initialQuery: string;
  includeArchived: boolean;
};

export function WorkspacePageClient({
  initialProjects,
  initialQuery,
  includeArchived,
}: WorkspacePageClientProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);

  async function handleCreateProject() {
    setError(null);
    try {
      const project = await createProject({
        name,
        description,
        default_external_policy: "allow_external",
      });
      router.push(`/projects/${project.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "创建项目失败。");
    }
  }

  function handleSearch() {
    startTransition(() => {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("query", query.trim());
      }
      if (includeArchived) {
        params.set("includeArchived", "true");
      }
      router.push(`/workspace${params.toString() ? `?${params.toString()}` : ""}`);
    });
  }

  const projects = initialProjects;

  return (
    <div className={styles.layout}>
      <section className={styles.createCard}>
        <div>
          <p className={styles.eyebrow}>创建项目</p>
          <h2 className={styles.cardTitle}>先建立一个知识库容器，再进入对话</h2>
          <p className={styles.cardBody}>新项目会直接进入聊天空态页，你可以先开会话，也可以稍后再补资料。</p>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>项目名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：Android 安装排障" />
          </label>
          <label className={styles.field}>
            <span>项目描述</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="一句话说明这个项目会沉淀什么资料、处理什么问题。"
              rows={3}
            />
          </label>
        </div>

        <div className={styles.createActions}>
          <button
            className={styles.primaryButton}
            disabled={isPending || !name.trim() || !description.trim()}
            onClick={handleCreateProject}
            type="button"
          >
            创建项目
          </button>
          {error ? <span className={styles.errorText}>{error}</span> : null}
        </div>
      </section>

      <section className={styles.listHeader}>
        <div>
          <h2 className={styles.sectionTitle}>最近活跃项目</h2>
          <p className={styles.sectionHint}>项目按最近活跃排序。进入项目后，再在左侧切换项目内会话。</p>
        </div>
        <div className={styles.searchBar}>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSearch();
              }
            }}
            placeholder="搜索项目名"
          />
          <button className={styles.secondaryButton} disabled={isPending} onClick={handleSearch} type="button">
            搜索
          </button>
        </div>
      </section>

      <div className={styles.projectGrid}>
        {projects.map((project) => (
          <Link key={project.id} className={styles.projectCard} href={`/projects/${project.id}`}>
            <div className={styles.projectCardHeader}>
              <span className={styles.projectName}>{project.name}</span>
              <span className={styles.projectMeta}>{project.active_source_count} 份资料</span>
            </div>
            <p className={styles.projectDescription}>{project.description}</p>
            <div className={styles.projectFooter}>
              <span>{project.active_session_count} 个会话</span>
              <span>{project.latest_session_title ?? "还没有会话"}</span>
            </div>
          </Link>
        ))}
        {!projects.length ? <div className={styles.emptyState}>当前没有命中的项目。你可以先创建一个新的知识库项目。</div> : null}
      </div>
    </div>
  );
}
