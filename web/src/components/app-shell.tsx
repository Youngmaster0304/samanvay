"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { History, Info, LayoutDashboard, Map, Moon, Database, Sun, TriangleAlert } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
      <Image
        src="/logo-mark.png"
        alt=""
        width={22}
        height={22}
        aria-hidden="true"
        style={{ display: "block", flexShrink: 0, width: 22, height: 22 }}
      />
      <span
        style={{
          fontFamily: "var(--font-stack-serif)",
          fontSize: `${size}px`,
          lineHeight: `${size + 4}px`,
          fontWeight: 600,
        }}
      >
        Samanvay
      </span>
    </span>
  );
}

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/map", label: "Map", icon: Map },
  { href: "/queue/conflicts", label: "Conflicts", icon: TriangleAlert },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/changes", label: "Changes", icon: History },
  { href: "/about", label: "About", icon: Info },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

const THEME_KEY = "samanvay-theme";
const THEME_EVENT = "samanvay-theme";

function readNight(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.dataset.theme === "night";
}

function subscribeTheme(onChange: () => void): () => void {
  window.addEventListener(THEME_EVENT, onChange);
  return () => window.removeEventListener(THEME_EVENT, onChange);
}

function applyNight(next: boolean) {
  if (next) document.documentElement.dataset.theme = "night";
  else delete document.documentElement.dataset.theme;
  try {
    localStorage.setItem(THEME_KEY, next ? "night" : "day");
  } catch {
    /* storage unavailable: the theme still applies for this session */
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** Restores the persisted theme on load. Syncs an external system, so no state. */
function useRestoredTheme() {
  useEffect(() => {
    try {
      if (localStorage.getItem(THEME_KEY) === "night" && !readNight()) applyNight(true);
    } catch {
      /* storage unavailable: start in day theme */
    }
  }, []);
}

function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const night = useSyncExternalStore(subscribeTheme, readNight, () => false);
  const Icon = night ? Sun : Moon;

  return (
    <button
      type="button"
      className="btn btn--secondary"
      style={{ minHeight: compact ? 36 : 40, padding: compact ? "0 10px" : "0 14px" }}
      onClick={() => applyNight(!night)}
      aria-pressed={night}
    >
      <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
      {compact ? null : night ? "Day" : "Night"}
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useRestoredTheme();

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <nav
        aria-label="Sections"
        className="hidden md:flex"
        style={{
          position: "fixed",
          inset: "0 auto 0 0",
          width: "208px",
          flexDirection: "column",
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
          zIndex: 20,
        }}
      >
        <Link
          href="/"
          className="small"
          style={{ display: "block", padding: "18px 16px", textDecoration: "none", color: "var(--text)" }}
        >
          <Wordmark />
        </Link>

        <div style={{ display: "grid", gap: "2px", padding: "8px" }}>
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className="small"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  minHeight: "40px",
                  padding: "0 10px",
                  textDecoration: "none",
                  color: active ? "var(--ink-900)" : "var(--text-muted)",
                  background: active ? "var(--marigold-100)" : "transparent",
                  borderLeft: `2px solid ${active ? "var(--marigold-500)" : "transparent"}`,
                  fontWeight: active ? 600 : 400,
                }}
              >
                <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </div>

        <div style={{ marginTop: "auto", padding: "12px", display: "grid", gap: "8px" }}>
          <p className="label" style={{ color: "var(--text-muted)", margin: 0 }}>
            Prototype · SIH 2026
          </p>
          <ThemeToggle />
        </div>
      </nav>

      <header
        className="md:hidden flex"
        style={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "10px 14px",
          background: "var(--surface)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <Link href="/" style={{ textDecoration: "none", color: "var(--text)" }}>
          <Wordmark size={18} />
        </Link>
        <ThemeToggle compact />
      </header>

      <main className="md:pl-52 px-4 pt-5 pb-24 md:pr-8 md:pb-10">
        {children}
      </main>

      <nav
        aria-label="Sections"
        className="md:hidden grid"
        style={{
          position: "fixed",
          inset: "auto 0 0 0",
          gridTemplateColumns: `repeat(${NAV.length}, minmax(0, 1fr))`,
          background: "var(--surface)",
          borderTop: "1px solid var(--border)",
          zIndex: 20,
        }}
      >
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "3px",
                minHeight: "56px",
                padding: "6px 0",
                minWidth: 0,
                overflow: "hidden",
                textDecoration: "none",
                fontSize: "10px",
                lineHeight: "13px",
                whiteSpace: "nowrap",
                color: active ? "var(--ink-900)" : "var(--text-muted)",
                background: active ? "var(--marigold-100)" : "transparent",
                borderTop: `2px solid ${active ? "var(--marigold-500)" : "transparent"}`,
                fontWeight: active ? 600 : 400,
              }}
            >
              <Icon size={18} strokeWidth={1.5} aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
