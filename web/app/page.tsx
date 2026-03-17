import Link from "next/link";
import MacroPanel from "@/components/MacroPanel";
import BigTechDropPanel from "@/components/BigTechDropPanel";

function EntryCard({
  eyebrow,
  title,
  description,
  href,
  tone = "accent",
}: {
  eyebrow: string;
  title: string;
  description: string;
  href: string;
  tone?: "accent" | "buy" | "sell";
}) {
  const toneColor =
    tone === "buy" ? "var(--buy)" : tone === "sell" ? "var(--sell)" : "var(--accent)";

  return (
    <Link
      href={href}
      className="glass-card block transition-transform duration-200 hover:-translate-y-1"
      style={{ borderRadius: 24, padding: 24 }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.24em]"
        style={{ color: toneColor }}
      >
        {eyebrow}
      </p>
      <h2 className="mt-3 text-2xl font-bold" style={{ color: "var(--foreground)" }}>
        {title}
      </h2>
      <p className="mt-3 text-sm leading-6" style={{ color: "var(--text-dim)" }}>
        {description}
      </p>
      <div className="mt-6 text-sm font-medium" style={{ color: toneColor }}>
        들어가기 →
      </div>
    </Link>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-8">
      <section
        className="glass-card overflow-hidden"
        style={{
          borderRadius: 28,
          padding: 32,
          background: "var(--hero-surface)",
        }}
      >
        <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-5">
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Overview
            </p>
            <div className="space-y-3">
              <h1 className="max-w-3xl text-4xl font-bold leading-tight" style={{ color: "var(--foreground)" }}>
                오늘의 마켓 보드
              </h1>
              <p className="max-w-2xl text-sm leading-7" style={{ color: "var(--text-dim)" }}>
                시장 요약을 먼저 보고 필요한 보드로 이동합니다.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              <span className="badge badge-accent">Overview = 빠른 상황판</span>
              <span className="badge badge-buy">Signals = 국내 종목 분석</span>
              <span className="badge badge-hold">Big Tech = 미국 스캐너</span>
            </div>
          </div>

          <div
            className="rounded-3xl p-5"
            style={{
              background: "var(--panel-muted)",
              border: "1px solid var(--panel-border-strong)",
            }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
              Operating Flow
            </p>
            <div className="mt-5 space-y-4">
              {[
                ["1", "US Big Tech", "빅테크 드로우다운 확인"],
                ["2", "KR Signals", "국내 종목 신호 점검"],
                ["3", "Autonomous", "운영 로그와 성과 확인"],
              ].map(([step, title, body]) => (
                <div key={step} className="flex gap-4">
                  <div
                    className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold"
                    style={{
                      background: "var(--chip-active-surface)",
                      border: "1px solid var(--chip-active-border)",
                      color: "var(--accent)",
                    }}
                  >
                    {step}
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                      {title}
                    </p>
                    <p className="mt-1 text-xs leading-5" style={{ color: "var(--text-dim)" }}>
                      {body}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-3">
        <EntryCard
          eyebrow="KR Signals"
          title="한국 주식 상세 분석"
          description="대표 종목 차트와 신호, 해석, 포지션 판단을 한 흐름으로 읽는 보드입니다."
          href="/signals"
          tone="buy"
        />
        <EntryCard
          eyebrow="US Big Tech"
          title="빅테크 마켓 스캐너"
          description="고점 대비 할인 폭과 액션 구간, 우선순위를 모아 보는 스캐너입니다."
          href="/bigtech"
          tone="accent"
        />
        <EntryCard
          eyebrow="Autonomous"
          title="자율매매 운영 콘솔"
          description="KR·US 운용 성과와 체결, 자산 흐름을 운영 관점에서 보는 콘솔입니다."
          href="/autonomous"
          tone="sell"
        />
      </section>

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Featured Scanner
            </p>
            <h2 className="mt-2 text-2xl font-bold" style={{ color: "var(--foreground)" }}>
              Big Tech Snapshot
            </h2>
            <p className="mt-2 text-sm leading-6" style={{ color: "var(--text-dim)" }}>
              할인율 분위기만 빠르게 보고 상세는 스캐너로 이동합니다.
            </p>
          </div>
          <Link href="/bigtech" className="text-sm font-medium" style={{ color: "var(--accent)" }}>
            전체 화면 열기 →
          </Link>
        </div>
        <BigTechDropPanel variant="preview" />
      </section>

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Macro
            </p>
            <h2 className="mt-2 text-2xl font-bold" style={{ color: "var(--foreground)" }}>
              Macro Snapshot
            </h2>
          </div>
          <Link href="/macro" className="text-sm font-medium" style={{ color: "var(--accent)" }}>
            Macro 화면 →
          </Link>
        </div>
        <MacroPanel />
      </section>
    </main>
  );
}
