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
          background:
            "radial-gradient(circle at top left, rgba(246,197,68,0.12), transparent 28%), linear-gradient(180deg, rgba(18,31,50,0.94) 0%, rgba(9,17,29,0.98) 100%)",
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
                지금 시장에서 먼저 볼 화면을 빠르게 고르는 대시보드입니다.
              </h1>
              <p className="max-w-2xl text-sm leading-7" style={{ color: "var(--text-dim)" }}>
                미국 빅테크 스캐너, 한국 종목 분석, 자율매매 운영, 매크로 체크포인트를 한 번에 훑고
                지금 필요한 작업 화면으로 바로 들어갈 수 있게 정리했습니다.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              <span className="badge badge-accent">Overview = 빠른 상황판</span>
              <span className="badge badge-buy">Signals = 종목 분석 워크스페이스</span>
              <span className="badge badge-hold">Big Tech = 미국 스캐너 전용</span>
            </div>
          </div>

          <div
            className="rounded-3xl p-5"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
              Recommended Flow
            </p>
            <div className="mt-5 space-y-4">
              {[
                ["1", "US Big Tech", "미국 빅테크 할인율과 드로우다운을 먼저 확인"],
                ["2", "KR Signals", "한국 종목 상세 차트와 신호를 읽기"],
                ["3", "Autonomous", "자동매매 상태와 성과를 운영 관점에서 점검"],
              ].map(([step, title, body]) => (
                <div key={step} className="flex gap-4">
                  <div
                    className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold"
                    style={{
                      background: "rgba(246,197,68,0.12)",
                      border: "1px solid rgba(246,197,68,0.22)",
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
          description="대표 종목 차트, RSI, MACD, AI 해석, 포지션 판단까지 한 흐름으로 읽는 분석 화면입니다."
          href="/signals"
          tone="buy"
        />
        <EntryCard
          eyebrow="US Big Tech"
          title="빅테크 마켓 스캐너"
          description="고점 대비 할인 폭, 분할매수 구간, 종목별 우선순위를 집중해서 보는 전용 화면입니다."
          href="/bigtech"
          tone="accent"
        />
        <EntryCard
          eyebrow="Autonomous"
          title="자율매매 운영 콘솔"
          description="KR/US 운용 성과, 체결 기록, 자산 흐름을 운영 로그 관점에서 점검하는 화면입니다."
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
              빅테크 스캐너는 홈 미리보기만 유지합니다.
            </h2>
            <p className="mt-2 text-sm leading-6" style={{ color: "var(--text-dim)" }}>
              상세 비교와 액션 해석은 전용 메뉴에서 보고, 홈에서는 오늘의 할인율 분위기만 빠르게 확인합니다.
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
              거시 지표는 별도 읽기 단위로 분리합니다.
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
