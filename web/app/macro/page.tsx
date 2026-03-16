import Link from "next/link";
import MacroPanel from "@/components/MacroPanel";
import SectionHeader from "@/components/SectionHeader";
import WorkspaceHero from "@/components/WorkspaceHero";

const focusCards = [
  {
    title: "Rates",
    body: "미국채 금리와 달러 방향을 함께 읽어 위험자산 압박 강도를 빠르게 판단합니다.",
  },
  {
    title: "Volatility",
    body: "변동성과 안전자산 움직임을 같이 봐서 신호 해석 전에 시장 온도를 맞춥니다.",
  },
  {
    title: "Commodities",
    body: "원유와 금의 동시 움직임으로 인플레이션과 회피 심리의 균형을 점검합니다.",
  },
];

export default function MacroPage() {
  return (
    <div className="min-h-screen" style={{ color: "var(--foreground)" }}>
      <WorkspaceHero
        eyebrow="Macro"
        title="MACRO PULSE DESK"
        description="금리, 달러, 변동성, 원자재 흐름을 한 보드에서 정리합니다."
        badges={["Rates · Dollar · Commodities", "Context Before Signals"]}
        actions={[
          { href: "/", label: "Overview" },
          { href: "/signals", label: "KR Signals" },
        ]}
        aside={
          <div className="space-y-4">
            <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
              Read Order
            </p>
            {focusCards.map((card, index) => (
              <div key={card.title} className="flex gap-4">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold"
                  style={{
                    background: "var(--chip-active-surface)",
                    border: "1px solid var(--chip-active-border)",
                    color: "var(--accent)",
                  }}
                >
                  {index + 1}
                </div>
                <div>
                  <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                    {card.title}
                  </p>
                  <p className="mt-1 text-xs leading-5" style={{ color: "var(--text-dim)" }}>
                    {card.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        }
      />

      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-8">
        <section className="grid gap-5 lg:grid-cols-3">
          {focusCards.map((card) => (
            <div
              key={card.title}
              className="glass-card rounded-[24px] p-6"
              style={{
                background: "var(--panel-surface-strong)",
              }}
            >
              <p
                className="text-[11px] font-semibold uppercase tracking-[0.24em]"
                style={{ color: "var(--accent)" }}
              >
                Focus
              </p>
              <h2 className="mt-3 text-xl font-bold" style={{ color: "var(--foreground)" }}>
                {card.title}
              </h2>
              <p className="mt-3 text-sm leading-6" style={{ color: "var(--text-dim)" }}>
                {card.body}
              </p>
            </div>
          ))}
        </section>

        <section className="space-y-4">
          <SectionHeader
            eyebrow="Dashboard"
            title="Macro Board"
            description="핵심 지표를 빠르게 훑는 실시간 보드입니다."
          />
          <MacroPanel />
        </section>

        <section
          className="glass-card flex flex-col gap-4 rounded-[24px] p-6 lg:flex-row lg:items-center lg:justify-between"
          style={{
            background: "var(--panel-surface-strong)",
          }}
        >
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Next Step
            </p>
            <h2 className="mt-2 text-2xl font-bold" style={{ color: "var(--foreground)" }}>
              Next Move
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
              컨텍스트를 맞춘 뒤 Signals나 Big Tech로 바로 이어집니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/signals" className="text-sm font-medium" style={{ color: "var(--accent)" }}>
              KR Signals →
            </Link>
            <Link href="/bigtech" className="text-sm font-medium" style={{ color: "var(--accent)" }}>
              US Big Tech →
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
