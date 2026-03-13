"""TradeRule.should_buy() 엣지 케이스 테스트.

버그 배경:
- rules.py:202 confluence_direction != "buy" 체크가 RSI 과매도 종목을
  무조건 차단하는 문제 발견 → exempt_scan_types 로직으로 수정됨.
- 역추세 매수 시 uptrend threshold 적용 확인.
- volume_surge / near_golden_cross 스캔도 면제 적용 확인.
- 포지션 한도 초과 시 거부 확인.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.rules import TradeRule, _get_entry_threshold
from tests.conftest import make_stock_data

from unittest.mock import patch
import config


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _rule(overrides=None):
    """overrides 없는 기본 TradeRule 인스턴스를 반환한다."""
    return TradeRule(rule_overrides=overrides or {})


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 역추세 매수 — 방향 체크 (rules.py:202)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCounterTrendBuyDirection:
    """direction이 "sell" 또는 "neutral"일 때 역추세 매수 허용/거부 로직."""

    def test_rsi_oversold_scan_with_buy_score_allows_counter_trend_buy(self):
        """sell 방향 + rsi_oversold 스캔 + buy_score > 0 → 역추세 매수 허용.

        역추세 매수 시 uptrend threshold(ENTRY_THRESHOLD_UPTREND=2.5)가 적용되므로
        buy_score는 2.5 이상이어야 한다.
        """
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=3.0,          # uptrend threshold(2.5) 초과
            confluence_score=0.0,   # sell 방향이므로 confluence_score는 의미 없음
            scan_signals=["rsi_oversold"],
            atr=1000,
            volume_ratio=1.0,
            regime="sideways",
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True, (
            f"역추세 매수가 허용돼야 한다. reason={result['reason']}"
        )

    def test_sell_direction_without_scan_signal_blocks_buy(self):
        """sell 방향 + scan_signals 없음 → 매수 차단."""
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=5.0,
            scan_signals=[],
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "매수 방향 아님" in result["reason"]

    def test_neutral_direction_without_scan_blocks_buy(self):
        """neutral 방향 + scan_signals 없음 → 매수 차단."""
        data = make_stock_data(
            confluence_direction="neutral",
            buy_score=5.0,
            scan_signals=[],
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False

    def test_sell_direction_rsi_oversold_but_zero_buy_score_blocks(self):
        """sell 방향 + rsi_oversold 스캔이지만 buy_score=0 → 매수 차단."""
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=0,
            scan_signals=["rsi_oversold"],
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "역추세 매수 신호 없음" in result["reason"]

    def test_volume_surge_scan_allows_counter_trend_buy(self):
        """sell 방향 + volume_surge 스캔 + buy_score > 0 → 역추세 매수 허용.

        역추세 매수 시 uptrend threshold(2.5)가 적용되므로 buy_score >= 2.5 필요.
        """
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=3.0,
            scan_signals=["volume_surge"],
            atr=1000,
            volume_ratio=1.0,
            regime="sideways",
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True, (
            f"volume_surge 스캔은 역추세 면제여야 한다. reason={result['reason']}"
        )

    def test_near_golden_cross_scan_allows_counter_trend_buy(self):
        """sell 방향 + near_golden_cross 스캔 + buy_score > 0 → 역추세 매수 허용.

        역추세 매수 시 uptrend threshold(2.5)가 적용되므로 buy_score >= 2.5 필요.
        """
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=3.0,
            scan_signals=["near_golden_cross"],
            atr=1000,
            volume_ratio=1.0,
            regime="sideways",
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True, (
            f"near_golden_cross 스캔은 역추세 면제여야 한다. reason={result['reason']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 역추세 매수 시 uptrend threshold 적용
# ═══════════════════════════════════════════════════════════════════════════════

class TestCounterTrendThreshold:
    """역추세 매수 시 레짐과 무관하게 uptrend threshold가 적용되는지 확인."""

    def test_counter_trend_uses_uptrend_threshold_not_downtrend(self):
        """downtrend 레짐에서 역추세 매수 시 downtrend 임계값(4.5)이 아닌
        uptrend 임계값(2.5)이 적용돼야 한다."""
        # uptrend threshold = 2.5, downtrend threshold = 4.5
        # buy_score=2.8 이면 uptrend(2.5) 통과, downtrend(4.5) 실패
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=2.8,
            scan_signals=["rsi_oversold"],
            regime="downtrend",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True, (
            f"역추세 매수는 uptrend threshold(2.5) 기준이어야 한다. "
            f"reason={result['reason']}"
        )

    def test_counter_trend_blocked_when_below_uptrend_threshold(self):
        """buy_score가 uptrend threshold(2.5)보다 낮으면 역추세 매수도 차단된다."""
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=1.0,  # uptrend threshold 2.5 미만
            scan_signals=["rsi_oversold"],
            regime="downtrend",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "합류 점수 부족" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 레짐별 threshold 적용
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegimeThresholds:
    """레짐별 매수 진입 점수 임계값이 올바르게 적용되는지 확인."""

    def test_uptrend_uses_lower_threshold(self):
        """uptrend 레짐은 낮은 임계값(2.5)을 사용한다."""
        # uptrend threshold = 2.5
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=2.6,
            buy_score=2.6,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True

    def test_sideways_blocks_below_threshold(self):
        """sideways 레짐에서 점수 3.5 미만은 차단된다."""
        # sideways threshold = 3.5
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=3.0,
            buy_score=3.0,
            regime="sideways",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "합류 점수 부족" in result["reason"]

    def test_downtrend_requires_high_threshold(self):
        """downtrend 레짐은 높은 임계값(4.5)이 필요하다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="downtrend",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "합류 점수 부족" in result["reason"]

    def test_downtrend_passes_above_threshold(self):
        """downtrend 레짐에서 점수 4.5 이상이면 통과한다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.6,
            buy_score=4.6,
            regime="downtrend",
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True

    def test_entry_threshold_override_takes_precedence(self):
        """set_entry_threshold_overrides()로 설정한 값이 기본값보다 우선된다."""
        rule = TradeRule(entry_threshold_overrides={"sideways": 1.0})
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=1.5,
            buy_score=1.5,
            regime="sideways",
            atr=1000,
            volume_ratio=1.0,
        )
        result = rule.should_buy(data)
        # override=1.0 이므로 1.5 > 1.0 → 통과
        assert result["recommend"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 추세 게이트 (MA / MACD)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrendGate:
    """MA_CROSS / MA_ALIGN / MACD 중 하나 이상 없으면 매수 차단."""

    def test_buy_blocked_when_no_trend_signal(self):
        """MA/MACD 시그널이 없으면 추세 게이트에서 차단된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            signals=[
                {"trigger": "RSI 과매도", "type": "buy", "source": "RSI",
                 "detail": "RSI 25", "strength": 1.0}
            ],
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "추세 확인 신호 없음" in result["reason"]

    def test_ma_align_source_passes_trend_gate(self):
        """MA_ALIGN source가 있으면 추세 게이트를 통과한다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            signals=[
                {
                    "trigger": "MA 상승 정렬",
                    "type": "buy",
                    "source": "MA_ALIGN",
                    "detail": "강한 상승 정렬",
                    "strength": 0.48,
                }
            ],
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True, (
            f"MA_ALIGN 시그널이 추세 게이트를 통과시켜야 한다. reason={result['reason']}"
        )

    def test_macd_trigger_passes_trend_gate(self):
        """'MACD 매수' trigger가 있으면 추세 게이트를 통과한다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            signals=[
                {
                    "trigger": "MACD 매수",
                    "type": "buy",
                    "source": "MACD",
                    "detail": "MACD 상향 돌파",
                    "strength": 1.0,
                }
            ],
            atr=1000,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True

    def test_scan_exempt_skips_trend_gate(self):
        """rsi_oversold 스캔 면제 종목은 추세 게이트를 건너뛴다."""
        data = make_stock_data(
            confluence_direction="sell",
            buy_score=3.0,
            scan_signals=["rsi_oversold"],
            # 추세 시그널 없음
            signals=[
                {"trigger": "RSI 과매도", "type": "buy", "source": "RSI",
                 "detail": "RSI 25", "strength": 1.0}
            ],
            atr=1000,
            volume_ratio=1.0,
            regime="sideways",
        )
        rule = _rule()
        result = rule.should_buy(data)
        # 추세 게이트 면제이므로 추세 시그널 없어도 통과
        assert result["recommend"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 거래량 필터
# ═══════════════════════════════════════════════════════════════════════════════

class TestVolumeFilter:
    """거래량 필터 엣지 케이스."""

    def test_low_volume_blocks_buy(self):
        """거래량 비율이 MIN_VOLUME_RATIO(0.7) 미만이면 차단된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            volume_ratio=0.5,  # 0.7 미만
            atr=1000,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "거래량 부족" in result["reason"]

    def test_volume_ratio_exactly_at_threshold_passes(self):
        """거래량 비율이 정확히 임계값이면 통과한다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            volume_ratio=0.7,  # 정확히 MIN_VOLUME_RATIO
            atr=1000,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True

    def test_min_volume_override_applied(self):
        """min_volume_ratio_override가 설정된 경우 해당 값을 사용한다."""
        rule = TradeRule(min_volume_ratio_override=0.3)
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            volume_ratio=0.4,  # 기본 0.7 미만이지만 override 0.3 초과
            atr=1000,
        )
        result = rule.should_buy(data)
        assert result["recommend"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 포지션 한도 초과
# ═══════════════════════════════════════════════════════════════════════════════

class TestPositionLimit:
    """최대 포지션 수 초과 시 매수 거부."""

    def test_exceeding_max_positions_blocks_buy(self):
        """현재 포지션 수가 MAX_POSITIONS(5)에 도달하면 매수가 거부된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
        )
        # MAX_POSITIONS=5개 채운 상태
        max_pos = config.MAX_POSITIONS
        current_positions = [
            {"ticker": f"00000{i}", "name": f"종목{i}"}
            for i in range(max_pos)
        ]
        rule = _rule()
        result = rule.should_buy(data, current_positions=current_positions)
        assert result["recommend"] is False
        assert "최대 보유 종목 초과" in result["reason"]

    def test_one_slot_remaining_allows_buy(self):
        """포지션 슬롯이 1개 남아 있으면 매수가 허용된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
        )
        max_pos = config.MAX_POSITIONS
        # max_pos - 1개 보유
        current_positions = [
            {"ticker": f"00000{i}", "name": f"종목{i}"}
            for i in range(max_pos - 1)
        ]
        rule = _rule()
        result = rule.should_buy(data, current_positions=current_positions)
        assert result["recommend"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ATR 기반 손절/목표가 계산
# ═══════════════════════════════════════════════════════════════════════════════

class TestATRCalculation:
    """ATR 기반 손절/목표가 계산 엣지 케이스."""

    def test_zero_atr_blocks_buy(self):
        """ATR이 0이면 매수를 거부한다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=0,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is False
        assert "ATR" in result["reason"]

    def test_stop_loss_respects_hard_cap(self):
        """ATR 손절가가 하드캡(8%)보다 낮으면 하드캡이 적용된다."""
        price = 10000
        # ATR이 매우 커서 손절가가 가격의 50% 아래로 떨어질 경우
        huge_atr = 8000
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            price=price,
            atr=huge_atr,
            volume_ratio=1.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True
        # 하드캡: price * (1 - 8/100) = 9200
        expected_hard_stop = int(price * (1 - config.MAX_LOSS_PCT / 100))
        assert result["stop_loss"] >= expected_hard_stop


# ═══════════════════════════════════════════════════════════════════════════════
# 8. VIX 기반 포지션 사이즈 조절
# ═══════════════════════════════════════════════════════════════════════════════

class TestVixPositionSizing:
    """VIX 수준에 따른 포지션 비중 조절."""

    def test_extreme_vix_reduces_position_size(self):
        """VIX > 30 (극단적 공포)이면 포지션 비중이 축소된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
            vix=35.0,
        )
        rule = _rule()
        result_extreme = rule.should_buy(data)

        data_no_vix = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
            vix=None,
        )
        result_normal = rule.should_buy(data_no_vix)

        assert result_extreme["recommend"] is True
        assert result_normal["recommend"] is True
        # 극단적 공포 시 비중이 더 작아야 한다
        assert result_extreme["weight_pct"] < result_normal["weight_pct"]

    def test_calm_vix_uses_full_position_size(self):
        """VIX < 15 (평온)이면 풀 사이즈 배수(1.0) 적용된다."""
        data = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
            vix=10.0,
        )
        rule = _rule()
        result = rule.should_buy(data)
        assert result["recommend"] is True
        # VIX_POSITION_MULT_CALM=1.0, TARGET_WEIGHT_PCT/SPLIT_BUY_PHASES
        expected_base = config.TARGET_WEIGHT_PCT / config.SPLIT_BUY_PHASES
        assert abs(result["weight_pct"] - expected_base) < 0.5
