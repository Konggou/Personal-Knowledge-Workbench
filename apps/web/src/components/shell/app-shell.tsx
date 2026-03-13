"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { topNavigation } from "@/lib/navigation";

import styles from "./app-shell.module.css";

type AppShellProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  headerClassName?: string;
  mainClassName?: string;
};

export function AppShell({ children, title, subtitle, actions, headerClassName, mainClassName }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <header className={`${styles.header} ${headerClassName ?? ""}`.trim()}>
        <Link className={styles.brand} href="/workspace">
          Personal Knowledge Workbench
        </Link>
        <nav className={styles.nav} aria-label="Primary">
          {topNavigation.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`.trim()}
                href={item.href}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
      {(title || subtitle || actions) ? (
        <section className={styles.hero}>
          <div>
            {title ? <h1 className={styles.title}>{title}</h1> : null}
            {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </section>
      ) : null}
      <main className={`${styles.main} ${mainClassName ?? ""}`.trim()}>{children}</main>
    </div>
  );
}
