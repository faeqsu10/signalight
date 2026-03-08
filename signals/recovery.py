"""회복 시그널 분석 모듈.

40% 이상 급락한 종목의 바닥 신호를 체크리스트 기반으로 분석한다.
'예측'이 아닌 '현황 판단' 원칙 — 과거 패턴 기반 참고 지표일 뿐, 투자 추천이 아닙니다.
"""
from typing import Dict, List, Optional, Tuple

import pandas as pd

from signals.indicators import (
    calc_rsi,
    calc_bollinger_bands,
    calc_obv,
    calc_volume_ratio,
    detect_volume_spike,
    detect_obv_divergence,
)
from config import (
    RSI_PERIOD,
    RSI_OVERSOLD,
    RECOVERY_RSI_EXTREME,
    RECOVERY_VOLUME_SPIKE,
    RECOVERY_LOOKBACK_DAYS,
    INVESTOR_CONSEC_DAYS,
)


# ---------- 데이터 모델 ----------

class RecoveryCheck:
    """개별 회복 체크리스트 항목."""

    def __init__(self, name: str, passed: bool, weight: float, detail: str):
        self.name = name
        self.passed = passed
        self.weight = weight
        self.detail = detail

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "weight": self.weight,
            "detail": self.detail,
        }


class DrawdownEpisode:
    """과거 낙폭 에피소드."""

    def __init__(
        self,
        peak_date: str,
        trough_date: str,
        peak_price: float,
        trough_price: float,
        drawdown_pct: float,
        recovery_days: Optional[int],
        recovered: bool,
    ):
        self.peak_date = peak_date
        self.trough_date = trough_date
        self.peak_price = peak_price
        self.trough_price = trough_price
        self.drawdown_pct = drawdown_pct
        self.recovery_days = recovery_days
        self.recovered = recovered

    def to_dict(self) -> Dict:
        return {
            "peak_date": self.peak_date,
            "trough_date": self.trough_date,
            "peak_price": self.peak_price,
            "trough_price": self.trough_price,
            "drawdown_pct": round(self.drawdown_pct, 1),
            "recovery_days": self.recovery_days,
            "recovered": self.recovered,
        }


class RecoveryAnalysis:
    """회복 분석 결과."""

    def __init__(
        self,
        score: float,
        checks: List[RecoveryCheck],
        interpretation: str,
        historical_episodes: List[DrawdownEpisode],
    ):
        self.score = score
        self.checks = checks
        self.interpretation = interpretation
        self.historical_episodes = historical_episodes

    def to_dict(self) -> Dict:
        return {
            "score": round(self.score, 1),
            "checks": [c.to_dict() for c in self.checks],
            "interpretation": self.interpretation,
            "historical_episodes": [e.to_dict() for e in self.historical_episodes],
            "disclaimer": "본 분석은 기술적 지표 기반 현황 판단이며, 투자 추천이 아닙니다. 투자 결정은 본인 책임입니다.",
        }


# ---------- 점수 해석 ----------

def _interpret_score(score: float) -> str:
    if score >= 9.0:
        return "강한 회복 신호 — 다수 바닥 지표 확인됨. 단, 추세 전환 확인 필요."
    elif score >= 6.0:
        return "복수 바닥 신호 — 일부 회복 조건 충족. 추가 확인 필요."
    elif score >= 3.0:
        return "초기 바닥 신호 — 일부 지표만 확인. 아직 하락 중일 수 있음."
    else:
        return "회복 신호 미감지 — 바닥 형성 증거 부족. 추가 하락 가능성 있음."


# ---------- 시장 맥락 분류 ----------

def classify_drawdown_context(
    stock_change_pct: float,
    market_change_pct: float,
) -> str:
    """낙폭 원인을 시장 전체 vs 개별 종목으로 분류.

    Args:
        stock_change_pct: 종목 수익률 (%, 음수=하락)
        market_change_pct: 시장 지수 수익률 (%, 음수=하락)

    Returns:
        'MARKET_WIDE' | 'SECTOR_WIDE' | 'INDIVIDUAL'
    """
    # 시장도 크게 하락 (종목 하락의 60% 이상이 시장 영향이면)
    if market_change_pct < -10 and abs(market_change_pct) >= abs(stock_change_pct) * 0.6:
        return "MARKET_WIDE"
    # 시장 하락 있지만 종목이 훨씬 더 하락
    elif market_change_pct < -5:
        return "SECTOR_WIDE"
    else:
        return "INDIVIDUAL"


# ---------- 포지션 액션 가이드 ----------

def get_position_action(
    signal_strength: str,
    pnl_pct: float,
) -> Dict:
    """신호 강도와 손익률을 기반으로 포지션 액션 가이드 반환.

    Args:
        signal_strength: 'strong_buy'|'buy'|'neutral'|'sell'|'strong_sell'
        pnl_pct: 현재 손익률 (%, 음수=손실)

    Returns:
        dict with action, reason, caution
    """
    # 큰 손실 + 매수 신호
    if pnl_pct <= -30 and signal_strength in ("strong_buy", "buy"):
        return {
            "action": "분할 추가 매수 검토",
            "reason": f"큰 손실({pnl_pct:+.1f}%) 상태이나 회복 시그널 감지. 물타기 가능.",
            "caution": "전체 포트폴리오 비중 확인 필수. 한 종목 과집중 주의.",
        }
    elif pnl_pct <= -30 and signal_strength in ("sell", "strong_sell"):
        return {
            "action": "손절 검토",
            "reason": f"큰 손실({pnl_pct:+.1f}%) + 추가 하락 신호. 손실 확대 방지 고려.",
            "caution": "감정적 결정 주의. 펀더멘탈 변화 여부 확인.",
        }
    elif pnl_pct <= -30:
        return {
            "action": "관망 (홀딩)",
            "reason": f"큰 손실({pnl_pct:+.1f}%) 상태이나 명확한 방향 신호 없음.",
            "caution": "추가 매수/매도 모두 보류. 추세 전환 확인 후 행동.",
        }
    # 보통 손실 (-10~-30%)
    elif pnl_pct <= -10 and signal_strength in ("strong_buy", "buy"):
        return {
            "action": "분할 추가 매수 검토",
            "reason": f"손실({pnl_pct:+.1f}%) 상태이나 매수 신호. 평단가 낮출 기회.",
            "caution": "전체 포트폴리오 비중 확인.",
        }
    elif pnl_pct <= -10 and signal_strength in ("sell", "strong_sell"):
        return {
            "action": "일부 손절 검토",
            "reason": f"손실({pnl_pct:+.1f}%) + 매도 신호. 추가 하락 가능성.",
            "caution": "전량 매도보다 일부 정리 후 관찰 권장.",
        }
    elif pnl_pct <= -10:
        return {
            "action": "관망 (홀딩)",
            "reason": f"손실({pnl_pct:+.1f}%) 중. 뚜렷한 방향 없음.",
            "caution": "인내심 필요. 손절가 사전 설정 권장.",
        }
    # 소폭 손실 또는 이익
    elif signal_strength in ("strong_buy", "buy"):
        return {
            "action": "보유 유지 또는 추가 매수",
            "reason": f"손익({pnl_pct:+.1f}%) + 매수 신호.",
            "caution": "비중 과대 주의.",
        }
    elif signal_strength in ("sell", "strong_sell"):
        return {
            "action": "일부 익절/손절 검토",
            "reason": f"손익({pnl_pct:+.1f}%) + 매도 신호.",
            "caution": "전체 매도보다 분할 매도 권장.",
        }
    else:
        return {
            "action": "보유 유지",
            "reason": f"손익({pnl_pct:+.1f}%). 뚜렷한 방향 없음.",
            "caution": "별도 행동 불필요.",
        }


# ---------- 핵심: 6항목 체크리스트 분석 ----------

def analyze_recovery(
    df: pd.DataFrame,
    investor_df: Optional[pd.DataFrame] = None,
) -> RecoveryAnalysis:
    """6개 회복 시그널 체크리스트를 분석하여 점수를 반환.

    체크리스트 (가중치 합계 = 8.5, 정규화 → 0-10):
    1. RSI 극단 과매도 (< 20)         — weight 1.5
    2. RSI 과매도 이탈 (30↑ 복귀)      — weight 1.5
    3. BB 하단밴드 복귀 (터치 후 반등)   — weight 1.5
    4. 거래량 급증 (투매/capitulation)  — weight 1.5
    5. OBV 상승 다이버전스             — weight 1.5
    6. 기관 매수 전환                  — weight 1.0

    Args:
        df: OHLCV DataFrame (pykrx 한글 컬럼: 시가, 고가, 저가, 종가, 거래량)
        investor_df: 외인/기관 순매수 DataFrame (optional)

    Returns:
        RecoveryAnalysis with score, checks, interpretation
    """
    checks = []  # type: List[RecoveryCheck]
    closes = df["종가"]
    volumes = df["거래량"]

    # 지표 계산
    rsi = calc_rsi(closes, RSI_PERIOD)
    bb_upper, bb_middle, bb_lower = calc_bollinger_bands(closes, 20, 2)
    obv = calc_obv(closes, volumes)

    current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    prev_rsi = float(rsi.iloc[-2]) if len(rsi) >= 2 and not pd.isna(rsi.iloc[-2]) else None

    # 1. RSI 극단 과매도 (< 20)
    rsi_extreme = False
    rsi_detail = "RSI 데이터 부족"
    if current_rsi is not None:
        rsi_extreme = current_rsi <= RECOVERY_RSI_EXTREME
        rsi_detail = f"RSI {current_rsi:.1f}" + (" — 극단 과매도 구간" if rsi_extreme else " — 정상 범위")
    checks.append(RecoveryCheck("RSI 극단 과매도", rsi_extreme, 1.5, rsi_detail))

    # 2. RSI 과매도 이탈 (이전에 30 이하였다가 현재 30 이상으로 복귀)
    rsi_escape = False
    escape_detail = "RSI 데이터 부족"
    if current_rsi is not None and prev_rsi is not None:
        rsi_escape = prev_rsi <= RSI_OVERSOLD and current_rsi > RSI_OVERSOLD
        if rsi_escape:
            escape_detail = f"RSI {prev_rsi:.1f} → {current_rsi:.1f} (과매도 이탈 확인)"
        else:
            escape_detail = f"RSI {current_rsi:.1f} — 과매도 이탈 미확인"
    checks.append(RecoveryCheck("RSI 과매도 이탈", rsi_escape, 1.5, escape_detail))

    # 3. BB 하단밴드 복귀 (최근 5일 내 터치 후 현재 밴드 위)
    bb_recovery = False
    bb_detail = "볼린저밴드 데이터 부족"
    if not pd.isna(bb_lower.iloc[-1]) and len(closes) >= 5:
        recent_touched = any(
            closes.iloc[-(i + 1)] <= bb_lower.iloc[-(i + 1)]
            for i in range(1, min(6, len(closes)))
            if not pd.isna(bb_lower.iloc[-(i + 1)])
        )
        current_above = closes.iloc[-1] > bb_lower.iloc[-1]
        bb_recovery = recent_touched and current_above
        if bb_recovery:
            bb_detail = "하단밴드 터치 후 반등 확인"
        elif recent_touched:
            bb_detail = "하단밴드 터치 중 — 아직 반등 미확인"
        else:
            bb_detail = "하단밴드 미접촉 — 해당 없음"
    checks.append(RecoveryCheck("BB 하단밴드 복귀", bb_recovery, 1.5, bb_detail))

    # 4. 거래량 급증 (투매 / capitulation)
    vol_spike = detect_volume_spike(volumes, RECOVERY_VOLUME_SPIKE)
    vol_ratio = calc_volume_ratio(volumes)
    vol_detail = f"거래량 비율 {vol_ratio:.1f}x" + (" — 투매 수준 급증" if vol_spike else " — 정상 범위")
    checks.append(RecoveryCheck("거래량 급증 (투매)", vol_spike, 1.5, vol_detail))

    # 5. OBV 상승 다이버전스
    obv_div = detect_obv_divergence(closes, obv, lookback=20)
    obv_detail = "OBV 상승 다이버전스 감지" if obv_div else "OBV 다이버전스 미감지"
    checks.append(RecoveryCheck("OBV 상승 다이버전스", obv_div, 1.5, obv_detail))

    # 6. 기관 매수 전환
    inst_buy = False
    inst_detail = "수급 데이터 없음"
    if investor_df is not None and len(investor_df) >= INVESTOR_CONSEC_DAYS:
        recent = investor_df.tail(INVESTOR_CONSEC_DAYS)
        inst_consec_buy = (recent["기관순매수"] > 0).all()
        if inst_consec_buy:
            inst_buy = True
            inst_detail = f"기관 {INVESTOR_CONSEC_DAYS}일 연속 순매수 전환"
        else:
            inst_detail = "기관 연속 순매수 미확인"
    checks.append(RecoveryCheck("기관 매수 전환", inst_buy, 1.0, inst_detail))

    # 점수 계산 (가중 합산, 0-10 정규화)
    max_weight = sum(c.weight for c in checks)  # 8.5
    raw_score = sum(c.weight for c in checks if c.passed)
    normalized_score = (raw_score / max_weight) * 10 if max_weight > 0 else 0

    interpretation = _interpret_score(normalized_score)

    # 과거 에피소드 (빈 리스트 — find_historical_drawdowns에서 별도 호출)
    return RecoveryAnalysis(
        score=normalized_score,
        checks=checks,
        interpretation=interpretation,
        historical_episodes=[],
    )


# ---------- 과거 낙폭 에피소드 ----------

def find_historical_drawdowns(
    df: pd.DataFrame,
    threshold_pct: float = -20.0,
) -> List[DrawdownEpisode]:
    """과거 낙폭 에피소드를 탐색한다.

    peak에서 threshold_pct 이상 하락한 구간을 찾아 회복 여부를 판단.

    Args:
        df: OHLCV DataFrame (최소 RECOVERY_LOOKBACK_DAYS 권장)
        threshold_pct: 낙폭 기준 (%, 기본 -20%)

    Returns:
        DrawdownEpisode 리스트
    """
    closes = df["종가"]
    episodes = []  # type: List[DrawdownEpisode]

    if len(closes) < 50:
        return episodes

    peak_price = closes.iloc[0]
    peak_idx = 0
    trough_price = closes.iloc[0]
    trough_idx = 0
    in_drawdown = False

    for i in range(1, len(closes)):
        price = closes.iloc[i]

        if not in_drawdown:
            if price > peak_price:
                peak_price = price
                peak_idx = i
            else:
                dd_pct = ((price - peak_price) / peak_price) * 100
                if dd_pct <= threshold_pct:
                    in_drawdown = True
                    trough_price = price
                    trough_idx = i
        else:
            if price < trough_price:
                trough_price = price
                trough_idx = i
            elif price >= peak_price:
                # 완전 회복
                recovery_days = i - trough_idx
                peak_date = str(closes.index[peak_idx].date()) if hasattr(closes.index[peak_idx], 'date') else str(closes.index[peak_idx])
                trough_date = str(closes.index[trough_idx].date()) if hasattr(closes.index[trough_idx], 'date') else str(closes.index[trough_idx])
                dd_pct = ((trough_price - peak_price) / peak_price) * 100

                episodes.append(DrawdownEpisode(
                    peak_date=peak_date,
                    trough_date=trough_date,
                    peak_price=float(peak_price),
                    trough_price=float(trough_price),
                    drawdown_pct=dd_pct,
                    recovery_days=recovery_days,
                    recovered=True,
                ))

                # 리셋
                peak_price = price
                peak_idx = i
                in_drawdown = False

    # 진행 중인 낙폭 에피소드
    if in_drawdown:
        peak_date = str(closes.index[peak_idx].date()) if hasattr(closes.index[peak_idx], 'date') else str(closes.index[peak_idx])
        trough_date = str(closes.index[trough_idx].date()) if hasattr(closes.index[trough_idx], 'date') else str(closes.index[trough_idx])
        dd_pct = ((trough_price - peak_price) / peak_price) * 100

        episodes.append(DrawdownEpisode(
            peak_date=peak_date,
            trough_date=trough_date,
            peak_price=float(peak_price),
            trough_price=float(trough_price),
            drawdown_pct=dd_pct,
            recovery_days=None,
            recovered=False,
        ))

    return episodes
