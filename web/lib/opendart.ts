/**
 * OpenDART (금융감독원 전자공시시스템) API 클라이언트
 * 기업 공시 데이터 조회 (재무제표, 배당, 주요 공시)
 */

export interface Disclosure {
  rcept_no: string;        // 접수번호
  corp_name: string;       // 회사명
  report_nm: string;       // 보고서명
  rcept_dt: string;        // 접수일자 (YYYYMMDD)
  flr_nm: string;          // 공시 제출인명
}

// WATCH_LIST 종목의 stock_code → corp_code 매핑
const CORP_CODE_MAP: Record<string, string> = {
  "005930": "00126380", // 삼성전자
  "000660": "00164779", // SK하이닉스
  "373220": "01438164", // LG에너지솔루션
  "006400": "00126362", // 삼성SDI
  "207940": "00907913", // 삼성바이오로직스
  "068270": "00421045", // 셀트리온
  "105560": "00688996", // KB금융
  "005380": "00164529", // 현대차
  "035420": "00266961", // NAVER
  "035720": "00401731", // 카카오
};

/**
 * stock_code를 corp_code로 변환
 */
export function getCorpCode(ticker: string): string | null {
  return CORP_CODE_MAP[ticker] ?? null;
}

/**
 * OpenDART에서 최근 공시 목록 조회
 * @param corpCode DART 고유 기업코드 (8자리)
 * @param count 조회할 공시 수 (기본 5)
 * @returns 공시 목록 또는 빈 배열 (API 키 없음/에러 시)
 */
export async function fetchDisclosures(
  corpCode: string,
  count: number = 5
): Promise<Disclosure[]> {
  const apiKey = process.env.DART_API_KEY;
  if (!apiKey) return [];

  try {
    const url = new URL("https://opendart.fss.or.kr/api/list.json");
    url.searchParams.set("crtfc_key", apiKey);
    url.searchParams.set("corp_code", corpCode);
    url.searchParams.set("page_count", String(count));

    const res = await fetch(url.toString(), { next: { revalidate: 3600 } });
    if (!res.ok) return [];

    const data = await res.json();
    if (data.status !== "000") return [];

    return (data.list ?? []).map((item: Record<string, string>) => ({
      rcept_no: item.rcept_no,
      corp_name: item.corp_name,
      report_nm: item.report_nm,
      rcept_dt: item.rcept_dt,
      flr_nm: item.flr_nm,
    }));
  } catch {
    return [];
  }
}

/**
 * 공시 날짜를 읽기 좋은 형식으로 변환
 * "20260308" → "2026.03.08"
 */
export function formatDisclosureDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd;
  return `${yyyymmdd.slice(0, 4)}.${yyyymmdd.slice(4, 6)}.${yyyymmdd.slice(6, 8)}`;
}

/**
 * 공시 상세 페이지 URL
 */
export function getDisclosureUrl(rceptNo: string): string {
  return `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rceptNo}`;
}
