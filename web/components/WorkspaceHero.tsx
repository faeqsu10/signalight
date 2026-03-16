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
    <section className="px-4 pt-8">
      <div
        className="mx-auto grid max-w-7xl gap-6 rounded-[28px] px-6 py-6 glass-card lg:grid-cols-[1.25fr_0.75fr]"
        style={{
          background:
            "radial-gradient(circle at top left, rgba(246,197,68,0.1), transparent 26%), linear-gradient(180deg, rgba(18,31,50,0.94) 0%, rgba(9,17,29,0.98) 100%)",
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
            <h1 className="mt-2 text-3xl font-bold tracking-[0.08em]" style={{ color: "var(--foreground)" }}>
              {title}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7" style={{ color: "var(--text-dim)" }}>
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
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.05)",
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
                    background: "rgba(246,197,68,0.08)",
                    border: "1px solid rgba(246,197,68,0.12)",
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
            className="rounded-3xl p-5"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            {aside}
          </div>
        )}
      </div>
    </section>
  );
}
