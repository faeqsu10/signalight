import BigTechDropPanel from "@/components/BigTechDropPanel";
import SectionHeader from "@/components/SectionHeader";
import WorkspaceHero from "@/components/WorkspaceHero";

const focusCards = [
  {
    title: "Drawdown",
    body: "52주 고점 대비 할인 폭을 기준으로 종목을 같은 축에서 비교합니다.",
  },
  {
    title: "Action Zones",
    body: "낙폭 구간을 분할매수 관점으로 빠르게 해석할 수 있게 정리합니다.",
  },
  {
    title: "Priority",
    body: "미국 빅테크만 모아서 지금 먼저 볼 종목 순서를 좁히는 데 집중합니다.",
  },
];

export default function BigTechPage() {
  return (
    <div className="min-h-screen" style={{ color: "var(--foreground)" }}>
      <WorkspaceHero
        eyebrow="US Big Tech"
        title="BIG TECH MARKET SCANNER"
        description="빅테크는 홈에서 요약으로만 소비할 정보가 아니라, 별도 스캐너로 읽어야 하는 작업 화면입니다. 여기서는 52주 고점 대비 낙폭과 매수 우선순위를 한 화면에서 비교합니다."
        badges={["Drawdown · Priority · Action", "US Scanner Focus"]}
        actions={[
          { href: "/", label: "Overview" },
          { href: "/autonomous", label: "Autonomous" },
        ]}
        aside={
          <div className="space-y-4">
            <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
              Reading Order
            </p>
            {focusCards.map((card, index) => (
              <div key={card.title} className="flex gap-4">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold"
                  style={{
                    background: "rgba(246,197,68,0.12)",
                    border: "1px solid rgba(246,197,68,0.22)",
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
                background:
                  "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
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
            eyebrow="Live Scanner"
            title="현재 할인율 비교"
            description="숫자와 게이지를 중심으로 읽도록 단순화한 전용 영역입니다. 홈 미리보기보다 더 직접적으로 종목 간 간격을 비교할 수 있습니다."
          />
          <BigTechDropPanel />
        </section>
      </main>
    </div>
  );
}
