import Link from "next/link";
import type { ReactNode } from "react";

type WorkspaceHeroAction = {
  href: string;
  label: string;
};

export default function WorkspaceHero({
  eyebrow,
  title,
  description,
  badges = [],
  actions = [],
  aside,
}: {
  eyebrow: string;
  title: string;
  description: string;
  badges?: string[];
  actions?: WorkspaceHeroAction[];
  aside?: ReactNode;
}) {
  return (
    <section className="px-4 pt-6 sm:pt-8">
      <div
        className="mx-auto grid max-w-7xl gap-5 rounded-[24px] px-5 py-5 glass-card sm:gap-6 sm:rounded-[28px] sm:px-6 sm:py-6 lg:grid-cols-[1.25fr_0.75fr]"
        style={{
          background: "var(--hero-surface)",
        }}
      >
        <div className="space-y-5">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.26em]"
              style={{ color: "var(--accent)" }}
            >
              {eyebrow}
            </p>
            <h1 className="mt-2 text-2xl font-bold tracking-[0.06em] sm:text-3xl sm:tracking-[0.08em]" style={{ color: "var(--foreground)" }}>
              {title}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 sm:leading-7" style={{ color: "var(--text-dim)" }}>
              {description}
            </p>
          </div>

          {(badges.length > 0 || actions.length > 0) && (
            <div className="flex flex-wrap items-center gap-2">
              {badges.map((badge) => (
                <span
                  key={badge}
                  className="rounded-full px-2.5 py-1 text-[11px]"
                  style={{
                    color: "var(--foreground)",
                    background: "var(--chip-surface)",
                    border: "1px solid var(--chip-border)",
                  }}
                >
                  {badge}
                </span>
              ))}
              {actions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="rounded-full px-2.5 py-1 text-[11px] font-medium transition-opacity hover:opacity-80"
                  style={{
                    color: "var(--accent)",
                    background: "var(--chip-active-surface)",
                    border: "1px solid var(--chip-active-border)",
                  }}
                >
                  {action.label}
                </Link>
              ))}
            </div>
          )}
        </div>

        {aside && (
          <div
            className="rounded-[22px] p-4 sm:rounded-3xl sm:p-5"
            style={{
              background: "var(--panel-muted)",
              border: "1px solid var(--panel-border-strong)",
            }}
          >
            {aside}
          </div>
        )}
      </div>
    </section>
  );
}
