import Link from "next/link";
import BigTechDropPanel from "@/components/BigTechDropPanel";

export default function BigTechPage() {
  return (
    <main className="max-w-6xl mx-auto px-4 py-10 space-y-6">
      <section
        className="glass-card"
        style={{
          borderRadius: 28,
          background:
            "radial-gradient(circle at top left, rgba(246,197,68,0.12), transparent 28%), linear-gradient(180deg, rgba(18,31,50,0.94) 0%, rgba(9,17,29,0.98) 100%)",
        }}
      >
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              US Big Tech
            </p>
            <h1 className="mt-2 text-3xl font-bold" style={{ color: "var(--foreground)" }}>
              빅테크 마켓 스캐너
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
              미국 빅테크 할인율을 독립된 스캐너처럼 다룹니다. 홈에서는 미리보기만 보고,
              여기서는 낙폭과 매수 우선순위를 집중해서 읽습니다.
            </p>
          </div>
          <Link
            href="/"
            className="text-sm font-medium transition-opacity hover:opacity-80"
            style={{ color: "var(--accent)" }}
          >
            ← Overview로 돌아가기
          </Link>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ["Drawdown", "52주 고점 대비 할인 폭으로 정렬", "var(--accent)"],
            ["Action", "구간별로 분할매수 해석을 빠르게 읽기", "var(--buy)"],
            ["Focus", "빅테크만 한 화면에 모아 비교", "var(--sell)"],
          ].map(([title, body, color]) => (
            <div
              key={title}
              className="rounded-2xl p-4"
              style={{
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <p className="text-sm font-semibold" style={{ color }}>
                {title}
              </p>
              <p className="mt-2 text-xs leading-5" style={{ color: "var(--text-dim)" }}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: "var(--accent)" }}
          >
            Live Scanner
          </p>
          <h1 className="mt-2 text-3xl font-bold" style={{ color: "var(--foreground)" }}>
            현재 할인율 비교
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
            고점 대비 할인 폭이 큰 종목을 한 번에 비교하는 전용 영역입니다. 숫자와 게이지를
            중심으로 읽도록 홈보다 더 직접적인 형태로 유지합니다.
          </p>
        </div>
        <Link
          href="/autonomous"
          className="text-sm font-medium transition-opacity hover:opacity-80"
          style={{ color: "var(--accent)" }}
        >
          Autonomous 보기 →
        </Link>
      </div>

      <BigTechDropPanel />
    </main>
  );
}
