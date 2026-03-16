import { Disclosure, formatDisclosureDate, getDisclosureUrl } from "@/lib/opendart";

interface Props {
  disclosures: Disclosure[] | null;
  loading: boolean;
}

function importanceBadge(reportName: string) {
  if (/영업.*실적|잠정.*실적|실적/.test(reportName)) {
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
        style={{
          background: "rgba(255,71,87,0.15)",
          color: "var(--sell)",
          border: "1px solid rgba(255,71,87,0.2)",
        }}
      >
        실적
      </span>
    );
  }
  if (/배당/.test(reportName)) {
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
        style={{
          background: "rgba(0,212,170,0.15)",
          color: "var(--buy)",
          border: "1px solid rgba(0,212,170,0.2)",
        }}
      >
        배당
      </span>
    );
  }
  if (/유상증자|무상증자|감자/.test(reportName)) {
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
        style={{
          background: "rgba(255,165,2,0.15)",
          color: "var(--hold)",
          border: "1px solid rgba(255,165,2,0.2)",
        }}
      >
        자본
      </span>
    );
  }
  if (/자기주식/.test(reportName)) {
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
        style={{
          background: "rgba(184,134,11,0.12)",
          color: "var(--accent)",
          border: "1px solid rgba(184,134,11,0.18)",
        }}
      >
        자사주
      </span>
    );
  }
  return null;
}

export default function DisclosurePanel({ disclosures, loading }: Props) {
  if (loading) {
    return (
      <div
        className="glass-card p-5"
        style={{
          borderRadius: 20,
          background: "var(--panel-surface-strong)",
        }}
      >
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--accent)" }}>공시 정보</h3>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-8 rounded animate-pulse"
              style={{ background: "var(--glass)" }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!disclosures || disclosures.length === 0) {
    return null;
  }

  return (
    <div
      className="glass-card p-5"
      style={{
        borderRadius: 20,
        background: "var(--panel-surface-strong)",
      }}
    >
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--accent)" }}>
        최근 공시 (DART)
      </h3>
      <ul className="space-y-1">
        {disclosures.map((d) => (
          <li key={d.rcept_no}>
            <a
              href={getDisclosureUrl(d.rcept_no)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2 text-sm rounded-xl px-3 py-2 transition-colors group"
              style={{ color: "var(--foreground)" }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--chip-surface)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span className="text-xs flex-shrink-0 pt-0.5" style={{ color: "var(--text-dim)" }}>
                {formatDisclosureDate(d.rcept_dt)}
              </span>
              <span className="flex-1 min-w-0">
                <span
                  className="line-clamp-1 transition-colors"
                  style={{ color: "var(--foreground)" }}
                  onMouseEnter={e => (e.currentTarget.style.color = "var(--accent)")}
                  onMouseLeave={e => (e.currentTarget.style.color = "var(--foreground)")}
                >
                  {d.report_nm}
                </span>
              </span>
              {importanceBadge(d.report_nm)}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-[10px] mt-2 text-right" style={{ color: "var(--text-dim)", opacity: 0.6 }}>
        출처: 금융감독원 전자공시시스템 (DART)
      </p>
    </div>
  );
}
