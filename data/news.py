"""네이버 금융 종목별 뉴스를 크롤링한다."""

from typing import List

import requests
from lxml import html


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def fetch_news(ticker: str, limit: int = 5) -> List[dict]:
    """네이버 금융 종목별 뉴스를 크롤링한다.

    URL: https://finance.naver.com/item/news_news.naver?code={ticker}&page=1

    Args:
        ticker: 종목코드 (예: "005930")
        limit: 반환할 최대 뉴스 수 (기본 5)

    Returns:
        List of dicts: [{"title": "뉴스 제목", "date": "2026.03.07", "url": "https://..."}]
        오류 시 빈 리스트 반환.
    """
    url = (
        f"https://finance.naver.com/item/news_news.naver"
        f"?code={ticker}&page=1&sm=title_entity_id.basic&clusterId="
    )

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.encoding = "euc-kr"
    except requests.RequestException:
        return []

    try:
        tree = html.fromstring(resp.text)
    except Exception:
        return []

    results = []  # type: List[dict]

    # type5 테이블 내 tbody의 tr 행을 순회한다.
    # 연관뉴스(relation_lst)와 relation_tit 클래스 tr은 제외하고,
    # td.title > a.tit 와 td.date 를 파싱한다.
    rows = tree.xpath('//table[contains(@class,"type5")]//tbody/tr')

    for tr in rows:
        # 연관뉴스 목록 행은 건너뛴다
        tr_class = tr.get("class", "")
        if "relation_lst" in tr_class:
            continue

        title_anchors = tr.xpath('.//td[@class="title"]/a[@class="tit"]')
        date_tds = tr.xpath('.//td[@class="date"]')

        if not title_anchors or not date_tds:
            continue

        anchor = title_anchors[0]
        raw_title = anchor.text_content().strip()
        href = anchor.get("href", "")

        # 상대 URL을 절대 URL로 변환한다.
        # href 예: /item/news_read.naver?article_id=...&office_id=...
        if href.startswith("/"):
            article_url = "https://finance.naver.com" + href
        else:
            article_url = href

        # article_id, office_id로 실제 네이버 뉴스 URL 구성 (가능하면)
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            office_id = params.get("office_id", [""])[0]
            article_id = params.get("article_id", [""])[0]
            if office_id and article_id:
                article_url = (
                    f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"
                )
        except Exception:
            pass

        raw_date = date_tds[0].text_content().strip()
        # 날짜 형식: "2026.03.08 01:12" → 날짜 부분만 추출
        date_part = raw_date.split(" ")[0] if " " in raw_date else raw_date

        results.append({
            "title": raw_title,
            "date": date_part,
            "url": article_url,
        })

        if len(results) >= limit:
            break

    return results
