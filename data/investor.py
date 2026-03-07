"""외인/기관 매매동향 데이터를 네이버 금융에서 가져온다."""

import time
from typing import Dict, List, Tuple

import pandas as pd
import requests
from lxml import html

# in-memory 캐시: {ticker: (timestamp, DataFrame)}
_cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 4 * 3600  # 4시간


def _parse_int(text: str) -> int:
    """숫자 문자열을 int로 변환한다. +/-/콤마 처리."""
    cleaned = text.replace(",", "").replace("+", "").strip()
    if not cleaned or cleaned == "-":
        return 0
    return int(cleaned)


def fetch_investor_trading(ticker: str, days: int = 20) -> pd.DataFrame:
    """외인/기관 순매수 데이터를 가져온다.

    네이버 금융의 외인/기관 매매동향 페이지를 파싱한다.
    URL: https://finance.naver.com/item/frgn.naver?code={ticker}

    Args:
        ticker: 종목코드 (예: "005930")
        days: 가져올 거래일 수 (기본 20일)

    Returns:
        DataFrame with columns: 외인순매수, 기관순매수 (index: 날짜)
        날짜 오름차순 정렬.
    """
    # 캐시 확인
    if ticker in _cache:
        cached_time, cached_df = _cache[ticker]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_df

    rows = []  # type: List[dict]
    pages_needed = (days // 20) + 2  # 한 페이지에 약 20행

    for page in range(1, pages_needed + 1):
        url = (
            f"https://finance.naver.com/item/frgn.naver"
            f"?code={ticker}&page={page}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "euc-kr"

        tree = html.fromstring(resp.text)

        # 두 번째 type2 테이블이 일별 데이터 테이블
        tables = tree.xpath('//table[@class="type2"]')
        if len(tables) < 2:
            break

        data_table = tables[1]
        trs = data_table.xpath('.//tr')

        for tr in trs:
            tds = tr.xpath('td')
            if len(tds) != 9:
                continue

            date_text = tds[0].text_content().strip()
            # 날짜 형식: "2026.03.06"
            if len(date_text) != 10 or date_text[4] != '.':
                continue

            try:
                inst_val = _parse_int(tds[5].text_content())
                frgn_val = _parse_int(tds[6].text_content())

                rows.append({
                    "날짜": pd.Timestamp(date_text),
                    "기관순매수": inst_val,
                    "외인순매수": frgn_val,
                })
            except (ValueError, IndexError):
                continue

        if len(rows) >= days:
            break

    if not rows:
        return pd.DataFrame(columns=["외인순매수", "기관순매수"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["날짜"])
    df = df.set_index("날짜")
    df = df.sort_index()  # 날짜 오름차순

    result = df.tail(days)
    _cache[ticker] = (time.time(), result)
    return result
