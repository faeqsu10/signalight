"""글로벌 매크로 가격 지표를 Yahoo Finance v8 chart API로 수집한다."""

import json
import logging
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import MACRO_CACHE_TTL, MACRO_EVENT_RULES, MACRO_INDICATORS

logger = logging.getLogger("signalight")

# in-memory 캐시
_macro_cache: Dict[str, Dict] = {}
_macro_cache_time: Optional[datetime] = None


def _encode_ticker(ticker: str) -> str:
    """Yahoo Finance ticker를 URL-safe하게 인코딩한다.

    예: ^TNX → %5ETNX, CL=F → CL%3DF
    """
    return urllib.parse.quote(ticker, safe="")


def fetch_macro_price(indicator_key: str, days: int = 30) -> Optional[Dict]:
    """단일 매크로 지표의 가격 데이터를 Yahoo Finance v8 chart API로 가져온다.

    Args:
        indicator_key: MACRO_INDICATORS의 키 (예: "WTI", "USDKRW")
        days: 조회 기간

    Returns:
        {
            "key": "WTI",
            "name": "WTI 원유",
            "unit": "USD/bbl",
            "price": 72.5,
            "prev_price": 70.0,
            "change_pct": 3.57,
            "threshold_pct": 5.0,
            "is_surge": False,
            "is_crash": False,
            "fetched_at": "2026-03-12T13:00:00",
        }
        또는 실패 시 None
    """
    if indicator_key not in MACRO_INDICATORS:
        logger.warning("Unknown macro indicator key: %s", indicator_key)
        return None

    cfg = MACRO_INDICATORS[indicator_key]
    ticker = cfg["ticker"]
    encoded = _encode_ticker(ticker)

    now = int(datetime.now().timestamp())
    from_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={from_ts}&period2={now}&interval=1d"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]

        # None 값 제거 후 최근 2개 확보
        valid_closes = [c for c in closes if c is not None]
        if len(valid_closes) < 2:
            logger.warning("Not enough data for %s (%s)", indicator_key, ticker)
            return None

        price = valid_closes[-1]
        prev_price = valid_closes[-2]
        change_pct = ((price - prev_price) / prev_price) * 100 if prev_price else 0.0

        threshold_pct = cfg["threshold_pct"]
        is_surge = change_pct >= threshold_pct
        is_crash = change_pct <= -threshold_pct

        return {
            "key": indicator_key,
            "name": cfg["name"],
            "unit": cfg["unit"],
            "price": round(price, 4),
            "prev_price": round(prev_price, 4),
            "change_pct": round(change_pct, 4),
            "threshold_pct": threshold_pct,
            "is_surge": is_surge,
            "is_crash": is_crash,
            "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }

    except Exception as e:
        logger.warning("Failed to fetch macro %s (%s): %s", indicator_key, ticker, e)
        return None


def fetch_all_macro_prices(days: int = 30) -> Dict[str, Dict]:
    """모든 매크로 지표를 병렬로 조회한다. 4시간 캐시 적용.

    Returns:
        {"WTI": {...}, "BRENT": {...}, ...}
        실패한 지표는 결과에서 제외된다.
    """
    global _macro_cache, _macro_cache_time

    # 캐시 유효 확인
    if _macro_cache_time is not None:
        elapsed = (datetime.now() - _macro_cache_time).total_seconds()
        if elapsed < MACRO_CACHE_TTL and _macro_cache:
            logger.debug("Returning cached macro data (%.0fs old)", elapsed)
            return _macro_cache

    keys = list(MACRO_INDICATORS.keys())
    results: Dict[str, Dict] = {}

    with ThreadPoolExecutor(max_workers=len(keys)) as executor:
        future_to_key = {
            executor.submit(fetch_macro_price, key, days): key for key in keys
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
                if result is not None:
                    results[key] = result
            except Exception as e:
                logger.warning("Macro fetch thread error for %s: %s", key, e)

    _macro_cache = results
    _macro_cache_time = datetime.now()
    logger.info("Fetched %d/%d macro indicators", len(results), len(keys))
    return results


def detect_macro_events(macro_data: Dict[str, Dict]) -> List[Dict]:
    """매크로 데이터에서 이벤트를 감지한다.

    config.py의 MACRO_EVENT_RULES를 기반으로 surge/crash 이벤트를 판별한다.

    Args:
        macro_data: fetch_all_macro_prices()의 반환값

    Returns:
        [{"event": "oil_surge", "source": "WTI", "change_pct": 5.2, "detail": "..."}, ...]
    """
    events: List[Dict] = []

    for key, rules in MACRO_EVENT_RULES.items():
        if key not in macro_data:
            continue

        indicator = macro_data[key]
        change_pct = indicator["change_pct"]
        name = indicator["name"]

        # surge 판별
        surge_event = rules.get("surge_event")
        if surge_event and change_pct >= rules["surge_pct"]:
            events.append({
                "event": surge_event,
                "source": key,
                "change_pct": change_pct,
                "detail": f"{name} {change_pct:+.2f}% (기준: +{rules['surge_pct']}%)",
            })

        # crash 판별
        crash_event = rules.get("crash_event")
        if crash_event and change_pct <= rules["crash_pct"]:
            events.append({
                "event": crash_event,
                "source": key,
                "change_pct": change_pct,
                "detail": f"{name} {change_pct:+.2f}% (기준: {rules['crash_pct']}%)",
            })

    return events
