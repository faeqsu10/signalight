import Link from "next/link";
import BigTechDropPanel from "@/components/BigTechDropPanel";

export default function BigTechPage() {
  return (
    <main className="max-w-6xl mx-auto px-4 py-10 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: "var(--accent)" }}
          >
            Dedicated View
          </p>
          <h1 className="mt-2 text-3xl font-bold" style={{ color: "var(--foreground)" }}>
            빅테크 할인율 상세 화면
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
            고점 대비 할인 폭이 큰 종목을 한 번에 비교하는 전용 페이지입니다. 홈 화면에서는
            요약만 보고, 여기서는 전체 게이지와 숫자를 집중해서 읽을 수 있게 구성했습니다.
          </p>
        </div>
        <Link
          href="/"
          className="text-sm font-medium transition-opacity hover:opacity-80"
          style={{ color: "var(--accent)" }}
        >
          ← 대시보드로 돌아가기
        </Link>
      </div>

      <BigTechDropPanel />
    </main>
  );
}
