import { Disclosure, formatDisclosureDate, getDisclosureUrl } from "@/lib/opendart";

interface Props {
  disclosures: Disclosure[] | null;
  loading: boolean;
}

/** 공시 유형별 중요도 뱃지 */
function importanceBadge(reportName: string) {
  if (/영업.*실적|잠정.*실적|실적/.test(reportName)) {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 flex-shrink-0">실적</span>;
  }
  if (/배당/.test(reportName)) {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400 flex-shrink-0">배당</span>;
  }
  if (/유상증자|무상증자|감자/.test(reportName)) {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 flex-shrink-0">자본</span>;
  }
  if (/자기주식/.test(reportName)) {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400 flex-shrink-0">자사주</span>;
  }
  return null;
}

export default function DisclosurePanel({ disclosures, loading }: Props) {
  if (loading) {
    return (
      <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
        <h3 className="text-sm font-semibold text-[var(--muted)] mb-3">공시 정보</h3>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-gray-200 dark:bg-zinc-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!disclosures || disclosures.length === 0) {
    return null;
  }

  return (
    <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
      <h3 className="text-sm font-semibold text-[var(--muted)] mb-3">
        최근 공시 (DART)
      </h3>
      <ul className="space-y-2">
        {disclosures.map((d) => (
          <li key={d.rcept_no}>
            <a
              href={getDisclosureUrl(d.rcept_no)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2 text-sm hover:bg-gray-50 dark:hover:bg-zinc-800/50 rounded px-2 py-1.5 -mx-2 transition-colors group"
            >
              <span className="text-xs text-[var(--muted)] flex-shrink-0 pt-0.5">
                {formatDisclosureDate(d.rcept_dt)}
              </span>
              <span className="flex-1 min-w-0">
                <span className="group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors line-clamp-1">
                  {d.report_nm}
                </span>
              </span>
              {importanceBadge(d.report_nm)}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-[10px] text-[var(--muted)] mt-2 text-right">
        출처: 금융감독원 전자공시시스템 (DART)
      </p>
    </div>
  );
}
