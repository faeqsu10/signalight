export interface InvestorData {
  date: string;
  foreignNet: number;
  institutionalNet: number;
}

/**
 * 네이버 금융에서 외국인/기관 순매수 데이터를 가져온다.
 * HTML을 파싱하여 테이블에서 데이터를 추출한다.
 * 서버 사이드(API route)에서만 호출해야 한다.
 */
export async function fetchInvestorData(
  ticker: string,
  pages: number = 1
): Promise<InvestorData[]> {
  const results: InvestorData[] = [];

  for (let page = 1; page <= pages; page++) {
    const url = `https://finance.naver.com/item/frgn.naver?code=${ticker}&page=${page}`;

    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0",
      },
    });

    if (!res.ok) {
      throw new Error(`Naver Finance API error: ${res.status}`);
    }

    const html = await res.text();
    const rows = parseInvestorTable(html);
    results.push(...rows);
  }

  return results;
}

/**
 * 네이버 금융 외인/기관 매매동향 HTML 테이블 파싱
 *
 * 테이블 구조 (type_2 클래스):
 * 날짜 | 종가 | 전일비 | 등락률 | 거래량 | 기관 순매매량 | 외국인 순매매량 | 외국인 보유주수 | 외국인 보유율
 */
function parseInvestorTable(html: string): InvestorData[] {
  const data: InvestorData[] = [];

  // type_2 테이블의 tbody 내 tr들에서 데이터 추출
  // 각 행의 td에서 날짜, 기관 순매매, 외국인 순매매를 가져온다
  const tableMatch = html.match(
    /<table[^>]*class="type2"[^>]*>([\s\S]*?)<\/table>/
  );
  if (!tableMatch) return data;

  const tableHtml = tableMatch[1];

  // 각 tr에서 데이터 추출
  const trRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/g;
  let trMatch;

  while ((trMatch = trRegex.exec(tableHtml)) !== null) {
    const trContent = trMatch[1];

    // td 추출
    const tdRegex = /<td[^>]*>([\s\S]*?)<\/td>/g;
    const tds: string[] = [];
    let tdMatch;
    while ((tdMatch = tdRegex.exec(trContent)) !== null) {
      tds.push(tdMatch[1]);
    }

    // 데이터 행은 최소 7개의 td를 가진다
    if (tds.length < 7) continue;

    // 날짜 추출 (span.tah 안의 텍스트 또는 직접 텍스트)
    const dateText = stripHtml(tds[0]).trim();
    const dateMatch = dateText.match(/(\d{4}\.\d{2}\.\d{2})/);
    if (!dateMatch) continue;

    const date = dateMatch[1].replace(/\./g, "-");

    // 기관 순매매량 (index 5), 외국인 순매매량 (index 6)
    const institutionalNet = parseNumber(stripHtml(tds[5]));
    const foreignNet = parseNumber(stripHtml(tds[6]));

    data.push({ date, foreignNet, institutionalNet });
  }

  return data;
}

/** HTML 태그 제거 */
function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

/** 한국식 숫자 문자열 파싱 (콤마 제거, +/- 처리) */
function parseNumber(text: string): number {
  const cleaned = text.replace(/,/g, "").replace(/\s/g, "").trim();
  const num = parseInt(cleaned, 10);
  return isNaN(num) ? 0 : num;
}
