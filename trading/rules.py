"""
룰 기반 매매 추천 엔진

실제 주문을 실행하지 않고, 시그널 데이터를 기반으로
매수/매도 추천 판단만 수행한다.
"""

from datetime import datetime, date
from typing import Dict, List, Optional

from config import (
    ENTRY_THRESHOLD_UPTREND, ENTRY_THRESHOLD_SIDEWAYS, ENTRY_THRESHOLD_DOWNTREND,
    MIN_VOLUME_RATIO,
    SPLIT_BUY_PHASES, SPLIT_BUY_CONFIRM_DAYS, SPLIT_BUY_PHASE3_BONUS,
    STOP_LOSS_ATR_UPTREND, STOP_LOSS_ATR_SIDEWAYS, STOP_LOSS_ATR_DOWNTREND,
    MAX_LOSS_PCT,
    TARGET1_ATR_MULT, TARGET2_ATR_MULT,
    TRAILING_STOP_ATR_MULT,
    MAX_HOLDING_DAYS,
    MAX_POSITIONS, MAX_EXPOSURE_PCT, MAX_SECTOR_POSITIONS,
    TARGET_WEIGHT_PCT, MAX_SINGLE_POSITION_PCT,
    VIX_POSITION_MULT_CALM, VIX_POSITION_MULT_NORMAL,
    VIX_POSITION_MULT_FEAR, VIX_POSITION_MULT_EXTREME,
    SECTOR_MAP,
)


def _get_entry_threshold(regime: str) -> float:
    """시장 레짐에 따른 매수 진입 점수 임계값을 반환한다."""
    if regime == "uptrend":
        return ENTRY_THRESHOLD_UPTREND
    elif regime == "downtrend":
        return ENTRY_THRESHOLD_DOWNTREND
    return ENTRY_THRESHOLD_SIDEWAYS


def _get_stop_loss_atr_mult(regime: str) -> float:
    """시장 레짐에 따른 손절 ATR 배수를 반환한다."""
    if regime == "uptrend":
        return STOP_LOSS_ATR_UPTREND
    elif regime == "downtrend":
        return STOP_LOSS_ATR_DOWNTREND
    return STOP_LOSS_ATR_SIDEWAYS


def _get_vix_position_mult(vix: Optional[float]) -> float:
    """VIX 수준에 따른 포지션 크기 배수를 반환한다."""
    if vix is None:
        return VIX_POSITION_MULT_NORMAL
    if vix > 30:
        return VIX_POSITION_MULT_EXTREME
    elif vix > 25:
        return VIX_POSITION_MULT_FEAR
    elif vix > 15:
        return VIX_POSITION_MULT_NORMAL
    return VIX_POSITION_MULT_CALM


def _has_trend_gate(signals: List[Dict]) -> bool:
    """매수 게이트: MA 크로스/정렬 또는 MACD 크로스 중 하나 이상 존재하는지 확인한다."""
    trend_sources = {"MA_CROSS", "MA_ALIGN", "MACD"}
    trend_triggers = {"골든크로스", "MACD 매수"}
    for sig in signals:
        if sig.get("type") != "buy":
            continue
        source = sig.get("source", "")
        trigger = sig.get("trigger", "")
        if source in trend_sources or trigger in trend_triggers:
            return True
    return False


class TradeRule:
    """룰 기반 매매 추천 판단 엔진.

    실제 주문을 실행하지 않는다. 시그널 데이터와 포지션 상태를 기반으로
    매수/매도 추천을 반환한다.
    """

    def should_buy(
        self,
        stock_data: Dict,
        current_positions: Optional[List[Dict]] = None,
        existing_position: Optional[Dict] = None,
    ) -> Dict:
        """매수 추천 여부를 판단한다.

        Args:
            stock_data: analyze_detailed() 반환값
            current_positions: 현재 보유 중인 포지션 리스트
            existing_position: 해당 종목의 기존 포지션 (분할 매수 판단용)

        Returns:
            {
                "recommend": bool,
                "action": str,  # "buy_phase1", "buy_phase2", "buy_phase3", "hold", "skip"
                "reason": str,
                "stop_loss": int,  # 손절가
                "target1": int,    # 1차 목표가
                "target2": int,    # 2차 목표가
                "weight_pct": float,  # 추천 비중 (%)
                "details": dict,  # 상세 정보
            }
        """
        ticker = stock_data.get("ticker", "")
        price = stock_data.get("price", 0)
        signals = stock_data.get("signals", [])
        indicators = stock_data.get("indicators", {})
        confluence_score = stock_data.get("confluence_score", 0)
        confluence_direction = stock_data.get("confluence_direction", "neutral")
        regime = stock_data.get("market_regime", "sideways")
        signal_strength = stock_data.get("signal_strength", "neutral")

        result = {
            "recommend": False,
            "action": "skip",
            "reason": "",
            "stop_loss": 0,
            "target1": 0,
            "target2": 0,
            "weight_pct": 0.0,
            "details": {},
        }

        # 1. 방향 체크: 매수 방향이 아니면 스킵
        if confluence_direction not in ("buy",):
            result["reason"] = "매수 방향 아님"
            return result

        # 2. 레짐별 점수 임계값 체크
        threshold = _get_entry_threshold(regime)
        if confluence_score < threshold:
            result["reason"] = f"합류 점수 부족 ({confluence_score:.1f} < {threshold})"
            result["details"]["threshold"] = threshold
            return result

        # 3. 추세 게이트 (MA/MACD 중 하나 이상 필요)
        if not _has_trend_gate(signals):
            result["reason"] = "추세 확인 신호 없음 (MA/MACD 필요)"
            return result

        # 4. 거래량 필터
        volume_ratio = indicators.get("volume_ratio", 1.0)
        if volume_ratio < MIN_VOLUME_RATIO:
            result["reason"] = f"거래량 부족 (평균 대비 {int(volume_ratio * 100)}%)"
            return result

        # 5. 포트폴리오 제한 체크
        if current_positions is not None:
            # 최대 동시 보유 종목 수
            if len(current_positions) >= MAX_POSITIONS:
                result["reason"] = f"최대 보유 종목 초과 ({MAX_POSITIONS}종목)"
                return result

            # 같은 섹터 제한
            sector = SECTOR_MAP.get(ticker, "기타")
            same_sector = sum(
                1 for p in current_positions
                if SECTOR_MAP.get(p.get("ticker", ""), "기타") == sector
            )
            if same_sector >= MAX_SECTOR_POSITIONS:
                result["reason"] = f"같은 섹터 초과 ({sector} {MAX_SECTOR_POSITIONS}종목)"
                return result

        # 6. ATR 기반 손절/목표가 계산
        atr = indicators.get("atr", 0)
        if atr <= 0:
            result["reason"] = "ATR 데이터 없음"
            return result

        stop_loss_mult = _get_stop_loss_atr_mult(regime)
        stop_loss = int(price - stop_loss_mult * atr)
        # 하드캡 적용
        hard_stop = int(price * (1 - MAX_LOSS_PCT / 100))
        stop_loss = max(stop_loss, hard_stop)

        target1 = int(price + TARGET1_ATR_MULT * atr)
        target2 = int(price + TARGET2_ATR_MULT * atr)

        # 7. VIX 기반 포지션 크기 조절
        vix = indicators.get("vix")
        vix_mult = _get_vix_position_mult(vix)
        base_weight = TARGET_WEIGHT_PCT / SPLIT_BUY_PHASES
        weight_pct = min(base_weight * vix_mult, MAX_SINGLE_POSITION_PCT)

        # 8. 분할 매수 단계 판단
        if existing_position is not None:
            phase = existing_position.get("phase", 1)
            entry_price = existing_position.get("entry_price", price)
            entry_date = existing_position.get("entry_date")

            if phase >= SPLIT_BUY_PHASES:
                result["reason"] = "분할 매수 완료 (3/3 단계)"
                result["action"] = "hold"
                return result

            if phase == 1:
                # Phase 2: 확인 대기 후 가격 > 진입가
                if entry_date:
                    days_held = _business_days_between(entry_date, date.today())
                    if days_held < SPLIT_BUY_CONFIRM_DAYS:
                        result["reason"] = f"Phase 2 대기 중 ({days_held}/{SPLIT_BUY_CONFIRM_DAYS}일)"
                        result["action"] = "hold"
                        return result
                if price <= entry_price:
                    result["reason"] = "Phase 2 조건 미충족 (가격 < 진입가)"
                    result["action"] = "hold"
                    return result

                result["action"] = "buy_phase2"
                result["reason"] = f"Phase 2 분할 매수 추천 (가격 확인 + {SPLIT_BUY_CONFIRM_DAYS}일 경과)"

            elif phase == 2:
                # Phase 3: 점수 추가 상승 또는 신고가
                if confluence_score >= threshold + SPLIT_BUY_PHASE3_BONUS:
                    result["action"] = "buy_phase3"
                    result["reason"] = f"Phase 3 분할 매수 추천 (점수 {confluence_score:.1f} ≥ {threshold + SPLIT_BUY_PHASE3_BONUS})"
                else:
                    result["reason"] = "Phase 3 조건 미충족"
                    result["action"] = "hold"
                    return result
        else:
            result["action"] = "buy_phase1"
            result["reason"] = f"Phase 1 매수 추천 (점수 {confluence_score:.1f}, 레짐: {regime})"

        result["recommend"] = True
        result["stop_loss"] = stop_loss
        result["target1"] = target1
        result["target2"] = target2
        result["weight_pct"] = round(weight_pct, 1)
        result["details"] = {
            "threshold": threshold,
            "regime": regime,
            "atr": atr,
            "stop_loss_mult": stop_loss_mult,
            "vix_mult": vix_mult,
            "signal_strength": signal_strength,
        }

        return result

    def should_sell(
        self,
        stock_data: Dict,
        position: Dict,
    ) -> Dict:
        """매도 추천 여부를 판단한다.

        Args:
            stock_data: analyze_detailed() 반환값
            position: 보유 포지션 정보
                {
                    "ticker", "entry_price", "entry_date", "entry_atr",
                    "phase", "stop_loss", "target1", "target2",
                    "highest_close", "shares_remaining_pct"
                }

        Returns:
            {
                "recommend": bool,
                "action": str,  # "stop_loss", "target1", "target2", "trailing", "time_exit", "signal_exit", "hold"
                "reason": str,
                "sell_pct": float,  # 매도 비율 (0~100)
                "details": dict,
            }
        """
        price = stock_data.get("price", 0)
        indicators = stock_data.get("indicators", {})
        signal_strength = stock_data.get("signal_strength", "neutral")
        confluence_score = stock_data.get("confluence_score", 0)
        confluence_direction = stock_data.get("confluence_direction", "neutral")
        regime = stock_data.get("market_regime", "sideways")

        entry_price = position.get("entry_price", price)
        entry_date = position.get("entry_date")
        entry_atr = position.get("entry_atr", 0)
        stop_loss = position.get("stop_loss", 0)
        target1 = position.get("target1", 0)
        target2 = position.get("target2", 0)
        highest_close = position.get("highest_close", price)
        target1_hit = position.get("target1_hit", False)
        target2_hit = position.get("target2_hit", False)

        result = {
            "recommend": False,
            "action": "hold",
            "reason": "",
            "sell_pct": 0,
            "details": {},
        }

        # 현재 수익률
        pnl_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # 1. 손절 체크 (최우선)
        if stop_loss > 0 and price <= stop_loss:
            result["recommend"] = True
            result["action"] = "stop_loss"
            result["reason"] = f"손절 ({price:,}원 ≤ {stop_loss:,}원, {pnl_pct:+.1f}%)"
            result["sell_pct"] = 100
            return result

        # 하드캡 손절
        if pnl_pct <= -MAX_LOSS_PCT:
            result["recommend"] = True
            result["action"] = "stop_loss"
            result["reason"] = f"최대 손실 한도 ({pnl_pct:.1f}% ≤ -{MAX_LOSS_PCT}%)"
            result["sell_pct"] = 100
            return result

        # 2. 역시그널 매도
        if signal_strength == "strong_sell":
            result["recommend"] = True
            result["action"] = "signal_exit"
            result["reason"] = f"강한 매도 시그널 (점수 {confluence_score:.1f})"
            result["sell_pct"] = 100
            return result

        if signal_strength == "sell" and confluence_direction == "sell":
            result["recommend"] = True
            result["action"] = "signal_exit"
            result["reason"] = f"매도 시그널 (점수 {confluence_score:.1f})"
            result["sell_pct"] = 50
            return result

        # 3. 목표가 도달
        if not target1_hit and target1 > 0 and price >= target1:
            result["recommend"] = True
            result["action"] = "target1"
            result["reason"] = f"1차 목표 도달 ({price:,}원 ≥ {target1:,}원, {pnl_pct:+.1f}%)"
            result["sell_pct"] = 33
            result["details"]["new_stop_loss"] = entry_price  # 본전 스탑으로 이동
            return result

        if not target2_hit and target2 > 0 and price >= target2:
            result["recommend"] = True
            result["action"] = "target2"
            result["reason"] = f"2차 목표 도달 ({price:,}원 ≥ {target2:,}원, {pnl_pct:+.1f}%)"
            result["sell_pct"] = 33
            return result

        # 4. 트레일링 스탑 (목표1 도달 후)
        if target1_hit and highest_close > 0:
            current_atr = indicators.get("atr", entry_atr)
            trailing_stop = int(highest_close - TRAILING_STOP_ATR_MULT * current_atr)

            if price <= trailing_stop:
                result["recommend"] = True
                result["action"] = "trailing"
                result["reason"] = f"트레일링 스탑 ({price:,}원 ≤ {trailing_stop:,}원, {pnl_pct:+.1f}%)"
                result["sell_pct"] = 100  # 나머지 전량
                return result

        # 5. 시간 기반 매도
        if entry_date:
            days_held = _business_days_between(entry_date, date.today())
            if days_held >= MAX_HOLDING_DAYS:
                if pnl_pct > 0:
                    result["recommend"] = True
                    result["action"] = "time_exit"
                    result["reason"] = f"보유 기간 초과 ({days_held}일, 이익 {pnl_pct:+.1f}%)"
                    result["sell_pct"] = 100
                    return result
                elif pnl_pct > -3.0:
                    result["recommend"] = True
                    result["action"] = "time_exit"
                    result["reason"] = f"보유 기간 초과 ({days_held}일, 소폭 손실 {pnl_pct:+.1f}%)"
                    result["sell_pct"] = 100
                    return result
                else:
                    # 큰 손실이면 스탑 타이트하게
                    result["reason"] = f"보유 {days_held}일, 손실 {pnl_pct:.1f}% — 스탑 타이트닝 권장"
                    current_atr = indicators.get("atr", entry_atr)
                    result["details"]["tightened_stop"] = int(price - 1.0 * current_atr)

        result["reason"] = result["reason"] or f"보유 유지 ({pnl_pct:+.1f}%)"
        return result


def _business_days_between(start_date, end_date) -> int:
    """두 날짜 사이의 영업일 수를 계산한다 (간략 버전)."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    days = 0
    current = start_date
    from datetime import timedelta
    while current < end_date:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 월~금
            days += 1
    return days
