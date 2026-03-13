"""공통 픽스처 및 헬퍼 함수."""

import os
import sys
import tempfile
import pytest

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def make_stock_data(
    ticker="005930",
    name="삼성전자",
    price=70000,
    confluence_score=3.0,
    confluence_direction="buy",
    buy_score=3.0,
    sell_score=0.0,
    regime="sideways",
    signal_strength="buy",
    scan_signals=None,
    signals=None,
    atr=1000,
    volume_ratio=1.0,
    vix=None,
):
    """TradeRule.should_buy() 에 전달할 stock_data 딕셔너리를 만든다."""
    if signals is None:
        signals = [
            {
                "trigger": "골든크로스",
                "type": "buy",
                "source": "MA_CROSS",
                "detail": "골든크로스",
                "strength": 1.0,
            }
        ]
    if scan_signals is None:
        scan_signals = []

    indicators = {
        "atr": atr,
        "volume_ratio": volume_ratio,
        "rsi": 35.0,
        "short_ma": 68000.0,
        "long_ma": 65000.0,
    }
    if vix is not None:
        indicators["vix"] = vix

    return {
        "ticker": ticker,
        "name": name,
        "price": price,
        "confluence_score": confluence_score,
        "confluence_direction": confluence_direction,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "market_regime": regime,
        "signal_strength": signal_strength,
        "scan_signals": scan_signals,
        "signals": signals,
        "indicators": indicators,
    }


@pytest.fixture
def tmp_db(tmp_path):
    """격리된 SQLite DB 경로를 제공하는 픽스처."""
    return str(tmp_path / "test.db")
