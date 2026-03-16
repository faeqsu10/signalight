import Link from "next/link";
import MacroPanel from "@/components/MacroPanel";

export default function MacroPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: "var(--accent)" }}
          >
            Dedicated View
          </p>
          <h1 className="mt-2 text-3xl font-bold" style={{ color: "var(--foreground)" }}>
            Macro Pulse
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
            시장 해석에 영향을 주는 매크로 지표만 따로 읽는 화면입니다. 홈에서는 요약만 보고,
            여기서는 변동성, 금리, 달러, 원자재 흐름을 집중해서 확인할 수 있습니다.
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

      <MacroPanel />
    </main>
  );
}
