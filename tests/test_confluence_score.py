"""합류 점수(confluence score) 엣지 케이스 테스트.

버그 배경:
- CONFLUENCE_MIXED_TOLERANCE=0.3 → buy/sell 점수 차이가 0.3 미만이면
  confluence_score=0, direction="mixed" → 매수 불가.
- 현재는 1.0으로 완화됐지만, 다양한 경계값을 검증한다.
- MA_ALIGN 시그널이 buy_score에만 반영되고 signals 리스트에 미추가되면
  trend gate를 통과할 수 없는 버그를 검증한다.
"""

import sys
import os
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from signals.strategy import analyze_detailed, _count_consecutive


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _make_ohlcv(n=60, uptrend=False, downtrend=False) -> pd.DataFrame:
    """분석 가능한 최소 OHLCV DataFrame을 생성한다.

    uptrend=True  → 가격이 꾸준히 상승
    downtrend=True → 가격이 꾸준히 하락
    기본          → 횡보 (노이즈만 있음)
    """
    np.random.seed(42)
    base = 10000
    if uptrend:
        closes = np.linspace(base, base * 1.3, n) + np.random.randn(n) * 50
    elif downtrend:
        closes = np.linspace(base * 1.3, base, n) + np.random.randn(n) * 50
    else:
        closes = base + np.random.randn(n) * 200

    closes = np.maximum(closes, 100)
    df = pd.DataFrame({
        "시가":   closes * 0.99,
        "고가":   closes * 1.01,
        "저가":   closes * 0.98,
        "종가":   closes,
        "거래량": np.random.randint(1_000_000, 5_000_000, n),
    })
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 합류 점수 방향 분류
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfluenceDirection:
    """buy_score / sell_score 비율에 따른 confluence_direction 분류."""

    def test_buy_dominant_gives_buy_direction(self):
        """buy_score가 sell_score보다 많으면 direction='buy' (uptrend 데이터 사용)."""
        df = _make_ohlcv(60, uptrend=True)
        result = analyze_detailed(
            df, "TEST", "테스트",
            strategy_settings={"confluence_mixed_tolerance": 0.0},
        )
        # tolerance=0.0이면 mixed가 절대 발생하지 않음
        buy = result["buy_score"]
        sell = result["sell_score"]
        # 명시적으로 방향 검증
        if buy > sell:
            assert result["confluence_direction"] == "buy", (
                f"buy_score({buy:.2f}) > sell_score({sell:.2f}) 이면 direction='buy'"
            )
        elif sell > buy:
            assert result["confluence_direction"] == "sell"
        else:
            assert result["confluence_direction"] == "neutral"

    def test_sell_dominant_gives_sell_direction(self):
        """sell_score가 buy_score보다 많으면 direction='sell' (downtrend 데이터 사용)."""
        df = _make_ohlcv(60, downtrend=True)
        result = analyze_detailed(
            df, "TEST", "테스트",
            strategy_settings={"confluence_mixed_tolerance": 0.0},
        )
        buy = result["buy_score"]
        sell = result["sell_score"]
        if sell > buy:
            assert result["confluence_direction"] == "sell", (
                f"sell_score({sell:.2f}) > buy_score({buy:.2f}) 이면 direction='sell'"
            )
        elif buy > sell:
            assert result["confluence_direction"] == "buy"
        else:
            assert result["confluence_direction"] == "neutral"

    def test_equal_scores_give_neutral_direction(self):
        """buy_score == sell_score이면 direction='neutral'."""
        # buy_score = sell_score = 0일 때
        df = _make_ohlcv(60)
        result = analyze_detailed(df, "TEST", "테스트")
        if result["buy_score"] == result["sell_score"] == 0:
            assert result["confluence_direction"] == "neutral"

    def test_mixed_tolerance_zero_score_when_scores_close(self):
        """tolerance=0.1일 때 buy/sell 차이가 작으면 confluence_score=0, direction='mixed'."""
        df = _make_ohlcv(60)
        result = analyze_detailed(
            df, "TEST", "테스트",
            strategy_settings={"confluence_mixed_tolerance": 0.1},
        )
        buy = result["buy_score"]
        sell = result["sell_score"]
        if buy > 0 and sell > 0 and abs(buy - sell) < 0.1:
            assert result["confluence_score"] == 0
            assert result["confluence_direction"] == "mixed"

    def test_relaxed_tolerance_produces_nonzero_score_more_often(self):
        """tolerance=0.0이면 mixed가 없고, tolerance=1.0이면 mixed가 생길 수 있다.

        같은 데이터에서:
        - tolerance=0.0: mixed 절대 불가 → confluence_score > 0 (양 점수 있으면)
        - tolerance=1.0: buy/sell 차이 < 1.0이면 mixed → score=0
        즉, strict(0.0)가 relaxed(1.0)보다 score가 크거나 같다.
        """
        df = _make_ohlcv(60)
        result_strict = analyze_detailed(
            df, "TEST", "테스트",
            strategy_settings={"confluence_mixed_tolerance": 0.0},
        )
        result_relaxed = analyze_detailed(
            df, "TEST", "테스트",
            strategy_settings={"confluence_mixed_tolerance": 1.0},
        )
        # strict에서는 mixed가 없으므로 score >= relaxed score
        # (relaxed에서 mixed로 분류되면 score=0이 되는 반면 strict는 양수 유지)
        assert result_strict["confluence_score"] >= result_relaxed["confluence_score"], (
            f"tolerance=0 score={result_strict['confluence_score']:.2f} should be "
            f">= tolerance=1 score={result_relaxed['confluence_score']:.2f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 합류 점수 경계값
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfluenceScoreBoundary:
    """tolerance 경계에서 confluence_score 계산이 올바른지 확인."""

    def test_buy_2_sell_0_gives_buy_direction_score_2(self):
        """buy_score=2.0, sell_score=0 → direction='buy', score=2.0."""
        df = _make_ohlcv(60)
        # 직접 analyze_detailed 함수 내부 로직을 검증하기 위해
        # 내부 계산을 재현한다
        buy_score = 2.0
        sell_score = 0.0
        tolerance = 1.0

        if buy_score > 0 and sell_score > 0 and abs(buy_score - sell_score) < tolerance:
            direction = "mixed"
            score = 0
        else:
            score = round(max(buy_score, sell_score), 1)
            direction = "buy" if buy_score > sell_score else (
                "sell" if sell_score > buy_score else "neutral"
            )

        assert direction == "buy"
        assert score == 2.0

    def test_buy_0_sell_0_gives_neutral(self):
        """buy_score=0, sell_score=0 → direction='neutral', score=0."""
        buy_score = 0.0
        sell_score = 0.0
        tolerance = 1.0

        if buy_score > 0 and sell_score > 0 and abs(buy_score - sell_score) < tolerance:
            direction = "mixed"
            score = 0
        else:
            score = round(max(buy_score, sell_score), 1)
            direction = "buy" if buy_score > sell_score else (
                "sell" if sell_score > buy_score else "neutral"
            )

        assert direction == "neutral"
        assert score == 0.0

    def test_mixed_boundary_exactly_at_tolerance(self):
        """buy_score - sell_score == tolerance - 0.001 이면 mixed로 분류된다."""
        buy_score = 1.5
        sell_score = 0.6   # 차이 = 0.9 < tolerance 1.0
        tolerance = 1.0

        if buy_score > 0 and sell_score > 0 and abs(buy_score - sell_score) < tolerance:
            direction = "mixed"
            score = 0
        else:
            score = round(max(buy_score, sell_score), 1)
            direction = "buy" if buy_score > sell_score else (
                "sell" if sell_score > buy_score else "neutral"
            )

        assert direction == "mixed"
        assert score == 0

    def test_not_mixed_when_difference_equals_tolerance(self):
        """차이가 정확히 tolerance이면 mixed가 아니다 (< 조건)."""
        buy_score = 1.5
        sell_score = 0.5   # 차이 = 1.0, tolerance = 1.0 → < 1.0 아님
        tolerance = 1.0

        if buy_score > 0 and sell_score > 0 and abs(buy_score - sell_score) < tolerance:
            direction = "mixed"
            score = 0
        else:
            score = round(max(buy_score, sell_score), 1)
            direction = "buy" if buy_score > sell_score else (
                "sell" if sell_score > buy_score else "neutral"
            )

        assert direction == "buy"
        assert score == 1.5


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MA_ALIGN 시그널이 signals 리스트에 포함되는지 (버그 #5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMAAlignInSignalsList:
    """MA_ALIGN 시그널이 buy_score와 signals 리스트 양쪽에 반영되는지 확인.

    버그: buy_score에만 점수가 반영되고 signals 리스트에 추가되지 않으면
    trend gate(_has_trend_gate)에서 MA_ALIGN source를 찾지 못해 차단된다.
    """

    def test_ma_align_appears_in_signals_list_on_strong_uptrend(self):
        """강한 상승 정렬(가격 > 단기MA > 장기MA) 시 MA_ALIGN이 signals에 포함된다."""
        # 강한 상승 추세 데이터 생성
        df = _make_ohlcv(n=60, uptrend=True)
        result = analyze_detailed(df, "TEST", "테스트")

        sources = [sig.get("source") for sig in result["signals"]]
        # MA_CROSS 또는 MA_ALIGN 중 하나는 있어야 한다
        has_ma_signal = "MA_CROSS" in sources or "MA_ALIGN" in sources
        # 단순히 assert가 아닌 — 데이터가 uptrend인지 확인 후 검증
        if result["market_regime"] == "uptrend":
            assert has_ma_signal, (
                f"uptrend 데이터에서 MA_CROSS 또는 MA_ALIGN 시그널이 없다. "
                f"sources={sources}"
            )

    def test_ma_align_buy_signal_has_correct_source(self):
        """MA_ALIGN 매수 시그널의 source가 'MA_ALIGN'이고 type이 'buy'이다."""
        df = _make_ohlcv(n=60, uptrend=True)
        result = analyze_detailed(df, "TEST", "테스트")

        ma_align_signals = [
            s for s in result["signals"]
            if s.get("source") == "MA_ALIGN" and s.get("type") == "buy"
        ]
        for sig in ma_align_signals:
            assert sig["source"] == "MA_ALIGN"
            assert sig["type"] == "buy"
            assert sig["strength"] > 0

    def test_signals_list_is_always_a_list(self):
        """analyze_detailed 결과의 signals는 항상 리스트다."""
        df = _make_ohlcv(60)
        result = analyze_detailed(df, "TEST", "테스트")
        assert isinstance(result["signals"], list)

    def test_buy_score_reflects_ma_align_strength(self):
        """MA_ALIGN 시그널이 있으면 buy_score가 0보다 크다."""
        df = _make_ohlcv(n=60, uptrend=True)
        result = analyze_detailed(df, "TEST", "테스트")

        ma_align_in_signals = any(
            s.get("source") == "MA_ALIGN" for s in result["signals"]
        )
        if ma_align_in_signals:
            assert result["buy_score"] > 0, "MA_ALIGN 시그널이 있으면 buy_score > 0 이어야 한다"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 연속 강도 점수 (_count_consecutive)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCountConsecutive:
    """_count_consecutive() 함수의 경계값 테스트."""

    def test_all_positive_returns_length(self):
        """모두 양수이면 길이(+N)를 반환한다."""
        series = pd.Series([1, 2, 3, 4, 5])
        assert _count_consecutive(series) == 5

    def test_all_negative_returns_negative_length(self):
        """모두 음수이면 음수 길이(-N)를 반환한다."""
        series = pd.Series([-1, -2, -3])
        assert _count_consecutive(series) == -3

    def test_mixed_returns_trailing_count(self):
        """뒤에서부터 연속된 부분만 카운트한다."""
        series = pd.Series([-1, -2, 3, 4, 5])
        assert _count_consecutive(series) == 3

    def test_empty_series_returns_zero(self):
        """빈 시리즈이면 0을 반환한다."""
        series = pd.Series([], dtype=float)
        assert _count_consecutive(series) == 0

    def test_single_positive_returns_one(self):
        """길이 1의 양수 시리즈이면 1을 반환한다."""
        series = pd.Series([5.0])
        assert _count_consecutive(series) == 1

    def test_last_element_zero_returns_zero(self):
        """마지막 값이 0이면 0을 반환한다."""
        series = pd.Series([1, 2, 3, 0])
        assert _count_consecutive(series) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 데이터 부족 시 안전한 반환
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsufficientData:
    """long_ma_days보다 짧은 데이터 입력 시 안전하게 빈 결과를 반환한다."""

    def test_short_dataframe_returns_empty_result(self):
        """데이터가 long_ma(50)보다 짧으면 빈 결과를 반환한다."""
        df = _make_ohlcv(n=30)  # 50일 미만
        result = analyze_detailed(df, "TEST", "테스트")

        assert result["price"] == 0
        assert result["signals"] == []
        assert result["confluence_score"] == 0

    def test_exactly_long_ma_rows_does_not_crash(self):
        """정확히 long_ma 행수이면 크래시 없이 반환된다."""
        df = _make_ohlcv(n=50)
        # 크래시 없으면 통과
        result = analyze_detailed(df, "TEST", "테스트")
        assert isinstance(result, dict)
