"""글로벌 매크로 RSS 뉴스 수집 + 이벤트 분류."""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple
from urllib.request import Request, urlopen

from config import MACRO_NEWS_CACHE_TTL, MACRO_NEWS_KEYWORDS, MACRO_RSS_FEEDS

logger = logging.getLogger("signalight")

# In-memory cache: key -> (timestamp, data)
_news_cache: Dict[str, Tuple[float, List[Dict]]] = {}


def fetch_rss_feed(feed_key: str) -> List[Dict]:
    """단일 RSS 피드에서 뉴스를 수집한다."""
    feed = MACRO_RSS_FEEDS.get(feed_key)
    if not feed:
        return []

    # Check cache
    cache_key = f"rss_{feed_key}"
    if cache_key in _news_cache:
        ts, data = _news_cache[cache_key]
        if time.time() - ts < MACRO_NEWS_CACHE_TTL:
            return data

    try:
        req = Request(feed["url"])
        req.add_header("User-Agent", "Signalight/1.0")
        resp = urlopen(req, timeout=10)
        xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = []

        # Standard RSS 2.0 parsing
        for item in root.findall(".//item")[:20]:  # Max 20 per feed
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")

            items.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description[:200],  # Truncate
                "source": feed["name"],
                "lang": feed["lang"],
            })

        _news_cache[cache_key] = (time.time(), items)
        logger.info("RSS 수집: %s → %d건", feed["name"], len(items))
        return items

    except Exception as e:
        logger.warning("RSS 수집 실패 (%s): %s", feed_key, e)
        return []


def fetch_all_macro_news() -> List[Dict]:
    """모든 RSS 피드에서 뉴스를 수집한다."""
    all_news = []
    for key in MACRO_RSS_FEEDS:
        news = fetch_rss_feed(key)
        all_news.extend(news)
    return all_news


def classify_news_events(news_items: List[Dict]) -> List[Dict]:
    """뉴스 제목/내용에서 매크로 이벤트를 분류한다.

    Returns:
        [{"event": "oil", "title": "...", "source": "...", "keywords_matched": [...]}]
    """
    events = []

    for item in news_items:
        text = f"{item['title']} {item.get('description', '')}".lower()

        for event_type, keywords in MACRO_NEWS_KEYWORDS.items():
            matched = [kw for kw in keywords if kw.lower() in text]
            if matched:
                events.append({
                    "event": event_type,
                    "title": item["title"],
                    "source": item["source"],
                    "lang": item["lang"],
                    "keywords_matched": matched,
                    "link": item.get("link", ""),
                })
                break  # One event per news item

    return events


def get_macro_news_summary() -> Dict:
    """매크로 뉴스 요약을 반환한다.

    Returns:
        {
            "total_news": int,
            "events": [{"event": str, "count": int, "titles": [str]}],
            "recent_headlines": [{"title": str, "source": str}],
        }
    """
    news = fetch_all_macro_news()
    events = classify_news_events(news)

    # Group by event type
    event_groups: Dict[str, Dict] = {}
    for e in events:
        etype = e["event"]
        if etype not in event_groups:
            event_groups[etype] = {"event": etype, "count": 0, "titles": []}
        event_groups[etype]["count"] += 1
        if len(event_groups[etype]["titles"]) < 3:  # Max 3 titles per event
            event_groups[etype]["titles"].append(e["title"])

    return {
        "total_news": len(news),
        "events": list(event_groups.values()),
        "recent_headlines": [
            {"title": n["title"], "source": n["source"]}
            for n in news[:10]  # Top 10 recent
        ],
    }
