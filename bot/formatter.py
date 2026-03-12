"""
텔레그램 메시지 포맷터

구조화된 시그널 데이터를 받아 텔레그램 HTML 포맷 메시지를 생성한다.
텔레그램 허용 HTML 태그: <b>, <i>, <code>, <pre>
한국 주식 색상 관례: 상승=🔴, 하락=🔵
"""

from datetime import datetime
from typing import List, Optional


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────

def _format_amount(amount: int) -> str:
    """원화 금액을 읽기 쉬운 단위로 변환한다.

    Examples:
        2300000000 -> "23억"
        800000000  -> "8억"
        50000000   -> "5000만"
        1500000    -> "150만"
    """
    if amount == 0:
        return "0"

    sign = "+" if amount > 0 else "-"
    abs_amount = abs(amount)

    if abs_amount >= 100_000_000:
        value = abs_amount / 100_000_000
        # 소수점이 필요한 경우 (예: 1.5억)
        if value == int(value):
            return f"{sign}{int(value)}억"
        return f"{sign}{value:.1f}억"
    elif abs_amount >= 10_000:
        value = abs_amount / 10_000
        if value == int(value):
            return f"{sign}{int(value)}만"
        return f"{sign}{value:.1f}만"
    else:
        return f"{sign}{abs_amount:,}"


def _format_shares(shares: int) -> str:
    """주식 수량을 읽기 쉬운 단위로 변환한다 (주 단위).

    Examples:
        1500000 -> "150만주"
        23000   -> "2.3만주"
        500     -> "500주"
    """
    if shares == 0:
        return "0주"

    abs_shares = abs(shares)

    if abs_shares >= 10_000:
        value = abs_shares / 10_000
        if value == int(value):
            return f"{int(value)}만주"
        return f"{value:.1f}만주"
    else:
        return f"{abs_shares:,}주"


def _format_price(price: int) -> str:
    """가격을 천 단위 콤마 포맷으로 변환한다.

    Examples:
        58000 -> "58,000"
        100   -> "100"
    """
    return f"{price:,}"


def _change_emoji(change_pct: float) -> str:
    """등락률에 맞는 이모지를 반환한다."""
    if change_pct > 0:
        return "🔴"
    elif change_pct < 0:
        return "🔵"
    return "⬜"


def _signal_emoji(signal_type: str) -> str:
    """시그널 타입에 맞는 이모지를 반환한다."""
    if signal_type == "buy":
        return "🟢 매수"
    elif signal_type == "sell":
        return "🔴 매도"
    return "⬜ 관망"


def _confluence_label(score: float, total: int, direction: str = "buy") -> str:
    """합류 점수를 텍스트로 변환한다."""
    if direction == "mixed" or score == 0:
        return "혼재"
    if total == 0:
        return "데이터 없음"
    ratio = score / total
    is_buy = direction == "buy"
    if ratio >= 0.8:
        return "강한 매수" if is_buy else "강한 매도"
    elif ratio >= 0.6:
        return "매수 우세" if is_buy else "매도 우세"
    elif ratio >= 0.4:
        return "중립"
    return "혼재"


def _rsi_label(rsi: float) -> str:
    """RSI 값에 대한 해석 레이블을 반환한다."""
    if rsi >= 70:
        return "과매수"
    elif rsi <= 30:
        return "과매도"
    return "중립"


def _vix_label(vix: float) -> str:
    """VIX 값에 대한 해석 레이블을 반환한다."""
    if vix >= 30:
        return "극단적 공포"
    elif vix >= 25:
        return "공포"
    elif vix <= 12:
        return "극단적 낙관"
    return "보통"


def _format_change(change_pct: float) -> str:
    """등락률을 포맷한다 (부호 포함)."""
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.1f}%"


def _progress_bar(score: float, total: float, width: int = 12) -> str:
    """합류 점수를 텍스트 프로그레스 바로 변환한다."""
    if total <= 0:
        return ""
    ratio = min(score / total, 1.0)
    filled = round(ratio * width)
    empty = width - filled
    pct = int(ratio * 100)
    return f"{'▓' * filled}{'░' * empty} {pct}%"


# 시그널 트리거별 쉬운 해석
_EASY_EXPLAIN = {
    "골든크로스": "단기선이 장기선 위로 → 상승 전환 신호",
    "데드크로스": "단기선이 장기선 아래로 → 하락 전환 신호",
    "RSI 과매도": "많이 빠져서 반등 가능 구간",
    "RSI 과매수": "많이 올라서 조정 가능 구간",
    "MACD 매수": "추세 상승 전환 신호",
    "MACD 매도": "추세 하락 전환 신호",
    "볼린저밴드 하단": "평소 가격대 이탈 → 반등 가능",
    "볼린저밴드 상단": "평소 가격대 이탈 → 과열 주의",
    "OBV 상승 다이버전스": "주가↓ 거래량↑ → 모으는 중",
    "StochRSI 과매도": "정밀 바닥 신호 → 반등 임박",
    "StochRSI 과매수": "정밀 천장 신호 → 조정 임박",
    "VIX 공포": "시장 공포 → 역발상 매수 기회",
    "VIX 주의": "시장 불안 → 매수 기회 가능",
    "VIX 과열": "시장 낙관 과열 → 경고",
    "외인 연속 매수": "외국인이 계속 매수 중",
    "외인 연속 매도": "외국인이 계속 매도 중",
    "기관 연속 매수": "기관이 계속 매수 중",
    "기관 연속 매도": "기관이 계속 매도 중",
}


DIVIDER = "━━━━━━━━━━━━━━━━━━━"
DIVIDER_THIN = "───────────────────"

# 매크로 변동률 경고 임계치 (절대값 %)
_MACRO_ALERT_THRESHOLD = 2.0


def _format_macro_value(value: float, unit: str) -> str:
    """매크로 지표 값을 단위에 맞게 포맷한다."""
    if unit == "$":
        return f"${value:,.1f}"
    elif unit == "₩":
        return f"₩{value:,.0f}"
    elif unit == "%":
        return f"{value:.2f}%"
    elif unit == "pt":
        return f"{value:.1f}pt"
    else:
        return f"{value:.2f}{unit}"


def _build_macro_section(macro_data: Optional[dict]) -> str:
    """글로벌 매크로 요약 섹션을 생성한다.

    Args:
        macro_data: fetch_all_macro_prices()의 반환값.
            구조: {
                "WTI": {"name": "WTI 원유", "price": 72.5, "change_pct": 3.6, "unit": "USD/bbl", ...},
                ...
            }
            None이면 빈 문자열 반환.

    Returns:
        섹션 블록 문자열 (비어 있으면 "").
    """
    if not macro_data:
        return ""

    # dict of dicts → list 변환 (fetch_all_macro_prices 형식)
    indicators = []
    for key, item in macro_data.items():
        if isinstance(item, dict):
            indicators.append(item)

    if not indicators:
        return ""

    lines = []
    lines.append("<b>━━━ 🌍 글로벌 매크로 ━━━</b>")

    for item in indicators:
        name = item.get("name", "")
        value = item.get("price", item.get("value"))
        change_pct = item.get("change_pct")
        unit = item.get("unit", "")

        if value is None:
            continue

        val_str = _format_macro_value(value, unit)

        if change_pct is not None:
            change_str = _format_change(change_pct)
            alert = " ⚠️" if abs(change_pct) >= _MACRO_ALERT_THRESHOLD else ""
            lines.append(f"{name}: {val_str} ({change_str}){alert}")
        else:
            lines.append(f"{name}: {val_str}")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 시장 온도 / 한줄 코멘트 빌더
# ──────────────────────────────────────────────

def _build_market_temperature(stock_data_list: List[dict]) -> str:
    """시장 전체 분위기를 요약하는 '시장 온도' 블록을 생성한다."""
    up_count = sum(1 for s in stock_data_list if s.get("change_pct", 0) > 0)
    down_count = sum(1 for s in stock_data_list if s.get("change_pct", 0) < 0)
    flat_count = len(stock_data_list) - up_count - down_count

    buy_signal_count = sum(
        1 for s in stock_data_list
        if any(sig.get("type") == "buy" for sig in s.get("signals", []))
    )
    sell_signal_count = sum(
        1 for s in stock_data_list
        if any(sig.get("type") == "sell" for sig in s.get("signals", []))
    )

    # VIX (첫 번째 종목의 indicators에서 가져옴)
    vix = None
    for s in stock_data_list:
        v = s.get("indicators", {}).get("vix")
        if v is not None:
            vix = v
            break

    lines = []
    lines.append("<b>━━━ 시장 온도 ━━━</b>")

    # VIX 라인
    if vix is not None:
        vix_lbl = _vix_label(vix)
        if vix >= 25:
            vix_emoji = "🥶"
        elif vix <= 12:
            vix_emoji = "🔥"
        else:
            vix_emoji = "😐"
        lines.append(f"{vix_emoji} VIX {vix:.1f} ({vix_lbl})")

    # 등락 요약
    total = len(stock_data_list)
    lines.append(f"감시 {total}종목 | 상승 {up_count} · 하락 {down_count} · 보합 {flat_count}")

    # 시그널 요약
    sig_parts = []
    if buy_signal_count > 0:
        sig_parts.append(f"매수 {buy_signal_count}건")
    if sell_signal_count > 0:
        sig_parts.append(f"매도 {sell_signal_count}건")
    if sig_parts:
        lines.append(f"오늘 시그널: {' · '.join(sig_parts)}")
    else:
        lines.append("오늘 시그널: 없음")

    return "\n".join(lines)


def _build_market_comment(stock_data_list: List[dict]) -> str:
    """시장 분위기를 룰 기반으로 한줄 코멘트로 생성한다.

    LLM 분석이 있으면 해당 내용을 우선 활용한다.
    """
    up_count = sum(1 for s in stock_data_list if s.get("change_pct", 0) > 0)
    down_count = sum(1 for s in stock_data_list if s.get("change_pct", 0) < 0)
    total = len(stock_data_list)

    # VIX
    vix = None
    for s in stock_data_list:
        v = s.get("indicators", {}).get("vix")
        if v is not None:
            vix = v
            break

    # 매수/매도 시그널 종목
    buy_names = [
        s["name"] for s in stock_data_list
        if any(sig.get("type") == "buy" for sig in s.get("signals", []))
    ]
    sell_names = [
        s["name"] for s in stock_data_list
        if any(sig.get("type") == "sell" for sig in s.get("signals", []))
    ]

    # LLM reasoning 수집
    llm_comments = []
    for s in stock_data_list:
        llm = s.get("llm_analysis")
        if llm and llm.get("reasoning"):
            llm_comments.append(f"{s['name']}: {llm['reasoning']}")

    # 룰 기반 코멘트 생성
    parts = []

    # 시장 분위기
    if total > 0:
        down_ratio = down_count / total
        if down_ratio >= 0.7:
            parts.append("전반적 약세장")
        elif down_ratio <= 0.3:
            parts.append("전반적 강세장")
        else:
            parts.append("혼조세 장세")

    # VIX 코멘트
    if vix is not None:
        if vix >= 30:
            parts.append("극단적 공포 구간으로 역발상 매수 기회 모색 가능")
        elif vix >= 25:
            parts.append("시장 공포 심리 지속 중")
        elif vix <= 12:
            parts.append("과도한 낙관, 과열 주의 필요")

    # 시그널 코멘트
    if buy_names and not sell_names:
        parts.append(f"{', '.join(buy_names)} 매수 기회 포착")
    elif sell_names and not buy_names:
        parts.append(f"{', '.join(sell_names)} 매도 압력 감지")
    elif buy_names and sell_names:
        parts.append(f"매수({', '.join(buy_names)})와 매도({', '.join(sell_names)}) 엇갈림")

    if not parts:
        parts.append("뚜렷한 방향성 없이 관망 구간")

    comment = ". ".join(parts) + "."

    lines = []
    lines.append("")
    lines.append("<b>━━━ 한줄 코멘트 ━━━</b>")
    lines.append(f"<i>\"{comment}\"</i>")

    # LLM 코멘트가 있으면 하나만 추가
    if llm_comments:
        lines.append(f"🤖 {llm_comments[0]}")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 주목 종목 블록 빌더 (브리핑용)
# ──────────────────────────────────────────────

def _build_spotlight_block(stock: dict) -> str:
    """시그널이 있는 주목 종목의 상세 블록을 생성한다 (브리핑용)."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    signals = stock.get("signals", [])
    confluence_score = stock.get("confluence_score", 0)
    total_indicators = stock.get("total_indicators", 0)
    direction = stock.get("confluence_direction", "buy")
    investor = stock.get("investor", {})

    emoji = _change_emoji(change_pct)
    change_str = _format_change(change_pct)
    price_str = _format_price(price)

    # 대표 시그널 타입
    buy_signals = [s for s in signals if s.get("type") == "buy"]
    sell_signals = [s for s in signals if s.get("type") == "sell"]

    if buy_signals and not sell_signals:
        header_emoji = "🟢"
        header_label = "매수 가능성 포착"
    elif sell_signals and not buy_signals:
        header_emoji = "🔴"
        header_label = "매도 압력 증가"
    else:
        header_emoji = "🟡"
        header_label = "매수·매도 혼재"

    lines = []
    lines.append(f"{header_emoji} <b>{name}</b> — {header_label}")
    lines.append(f"  {price_str}원 ({emoji}{change_str})")

    # 합류 점수 + 프로그레스 바
    if total_indicators > 0:
        label = _confluence_label(confluence_score, total_indicators, direction)
        bar = _progress_bar(confluence_score, total_indicators)
        lines.append(f"  합류 {confluence_score:.1f}/{total_indicators} ({label})")
        lines.append(f"  {bar}")

    # 핵심 근거 (시그널 트리거 + 수급 요약)
    reasons = []
    for sig in signals:
        trigger = sig.get("trigger", "")
        explain = _EASY_EXPLAIN.get(trigger, "")
        if explain:
            reasons.append(explain)
        else:
            reasons.append(trigger)

    # 수급 요약 추가
    foreign_consec = investor.get("foreign_consec_days", 0)
    inst_consec = investor.get("institutional_consec_days", 0)
    if foreign_consec and abs(foreign_consec) >= 3:
        direction_str = "매수" if foreign_consec > 0 else "매도"
        reasons.append(f"외인 {abs(foreign_consec)}일 연속 {direction_str}")
    if inst_consec and abs(inst_consec) >= 3:
        direction_str = "매수" if inst_consec > 0 else "매도"
        reasons.append(f"기관 {abs(inst_consec)}일 연속 {direction_str}")

    if reasons:
        lines.append(f"  → {' + '.join(reasons[:3])}")

    # 주요 지표 요약
    indicators = stock.get("indicators", {})
    indicator_parts = []
    rsi = indicators.get("rsi")
    if rsi is not None:
        rsi_lbl = _rsi_label(rsi)
        indicator_parts.append(f"RSI {rsi:.0f}({rsi_lbl})")
    macd_hist = indicators.get("macd_histogram")
    if macd_hist is not None:
        d = "▲" if macd_hist > 0 else "▼"
        indicator_parts.append(f"MACD {d}")
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None:
        indicator_parts.append(f"거래량 {int(vol_ratio * 100)}%")
    if indicator_parts:
        lines.append(f"  📊 {' · '.join(indicator_parts)}")

    # 뉴스 감성
    news = stock.get("news_sentiment")
    if news and news.get("sentiment") in ("긍정", "부정"):
        sent = news["sentiment"]
        conf = int(news.get("confidence", 0) * 100)
        s_emoji = "🟢" if sent == "긍정" else "🔴"
        lines.append(f"  {s_emoji} 뉴스 {sent} (신뢰도 {conf}%)")

    # AI 판단 (있으면)
    llm = stock.get("llm_analysis")
    if llm and llm.get("reasoning"):
        lines.append(f"  🤖 {llm['reasoning']}")

    # 매매 추천 요약 (있으면)
    rec = stock.get("trade_recommendation")
    if rec and rec.get("recommend"):
        action = rec.get("action", "")
        if action.startswith("buy_"):
            stop = rec.get("stop_loss", 0)
            target = rec.get("target1", 0)
            lines.append(f"  💡 분할 매수 추천 (손절 {stop:,}원 / 목표 {target:,}원)")
        elif action in ("stop_loss", "target1", "target2", "trailing", "time_exit", "signal_exit"):
            lines.append(f"  💡 매도 추천: {rec.get('reason', '')}")

    return "\n".join(lines)


def _build_compact_row(stock: dict) -> str:
    """시그널 없는 종목의 요약을 생성한다 (주요 지표 포함)."""
    name = stock.get("name", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    indicators = stock.get("indicators", {})
    investor = stock.get("investor", {})

    emoji = _change_emoji(change_pct)
    change_str = _format_change(change_pct)
    price_str = _format_price(price)

    # 핵심 지표 수집
    tags = []

    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            tags.append(f"RSI {rsi:.0f} 과매수")
        elif rsi <= 30:
            tags.append(f"RSI {rsi:.0f} 과매도")
        else:
            tags.append(f"RSI {rsi:.0f}")

    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None and vol_ratio > 1.5:
        tags.append(f"거래량 {int(vol_ratio * 100)}%")

    # 수급
    foreign_consec = investor.get("foreign_consec_days", 0)
    inst_consec = investor.get("institutional_consec_days", 0)
    if foreign_consec and abs(foreign_consec) >= 3:
        d = "매수" if foreign_consec > 0 else "매도"
        tags.append(f"외인{abs(foreign_consec)}일{d}")
    if inst_consec and abs(inst_consec) >= 3:
        d = "매수" if inst_consec > 0 else "매도"
        tags.append(f"기관{abs(inst_consec)}일{d}")

    # 뉴스 감성
    news = stock.get("news_sentiment")
    if news and news.get("sentiment") in ("긍정", "부정"):
        s_emoji = "🟢" if news["sentiment"] == "긍정" else "🔴"
        tags.append(f"뉴스{s_emoji}")

    tag_str = f"  ({' · '.join(tags)})" if tags else ""

    return f"{emoji}{change_str}  <b>{name}</b>  {price_str}원{tag_str}"


# ──────────────────────────────────────────────
# 시그널 알림 블록 빌더 (리디자인)
# ──────────────────────────────────────────────

def _build_signal_summary_sentence(stock: dict) -> str:
    """시그널 알림 상단의 핵심 요약 문장을 생성한다."""
    signals = stock.get("signals", [])
    indicators = stock.get("indicators", {})
    investor = stock.get("investor", {})

    buy_reasons = []
    sell_reasons = []

    for sig in signals:
        trigger = sig.get("trigger", "")
        explain = _EASY_EXPLAIN.get(trigger, trigger)
        if sig.get("type") == "buy":
            buy_reasons.append(explain)
        elif sig.get("type") == "sell":
            sell_reasons.append(explain)

    # 수급 정보 추가
    foreign_consec = investor.get("foreign_consec_days", 0)
    inst_consec = investor.get("institutional_consec_days", 0)
    if foreign_consec and foreign_consec >= 3:
        buy_reasons.append(f"외인 {foreign_consec}일 연속 매수")
    elif foreign_consec and foreign_consec <= -3:
        sell_reasons.append(f"외인 {abs(foreign_consec)}일 연속 매도")
    if inst_consec and inst_consec >= 3:
        buy_reasons.append(f"기관 {inst_consec}일 연속 매수")
    elif inst_consec and inst_consec <= -3:
        sell_reasons.append(f"기관 {abs(inst_consec)}일 연속 매도")

    parts = []
    if buy_reasons:
        parts.append(" + ".join(buy_reasons[:3]))
    if sell_reasons:
        parts.append(" + ".join(sell_reasons[:3]))

    if buy_reasons and not sell_reasons:
        conclusion = "기술적으로 반등 가능성이 높아진 구간입니다."
    elif sell_reasons and not buy_reasons:
        conclusion = "추가 하락 가능성에 주의가 필요합니다."
    else:
        conclusion = "매수·매도 신호가 혼재하여 신중한 판단이 필요합니다."

    if parts:
        summary = ", ".join(parts)
        return f"<i>\"{summary}.\n{conclusion}\"</i>"
    return f"<i>\"{conclusion}\"</i>"


def _build_recommendation_block(rec: dict, current_price: int) -> str:
    """매매 추천 액션 블록을 생성한다."""
    action = rec.get("action", "skip")
    reason = rec.get("reason", "")
    recommend = rec.get("recommend", False)

    lines = []

    if not recommend:
        # 매수 추천이 아닌 경우 (보유 중 매도 추천 포함)
        sell_action = rec.get("action", "")
        if sell_action in ("stop_loss", "target1", "target2", "trailing", "time_exit", "signal_exit"):
            sell_pct = rec.get("sell_pct", 0)
            action_labels = {
                "stop_loss": "🛑 손절 매도",
                "target1": "🎯 1차 목표 도달",
                "target2": "🎯 2차 목표 도달",
                "trailing": "📉 트레일링 스탑",
                "time_exit": "⏰ 보유 기간 초과",
                "signal_exit": "📊 역시그널 매도",
            }
            label = action_labels.get(sell_action, "매도")
            lines.append(f"<b>━━━ 💡 추천 액션 ━━━</b>")
            lines.append(f"{label}")
            lines.append(f" • {reason}")
            if sell_pct > 0:
                lines.append(f" • 매도 비율: {sell_pct}%")
        return "\n".join(lines)

    # 매수 추천
    stop_loss = rec.get("stop_loss", 0)
    target1 = rec.get("target1", 0)
    target2 = rec.get("target2", 0)
    weight_pct = rec.get("weight_pct", 0)
    details = rec.get("details", {})

    phase_labels = {
        "buy_phase1": "1단계 진입 (1/3)",
        "buy_phase2": "2단계 추가 (2/3)",
        "buy_phase3": "3단계 완성 (3/3)",
    }
    phase_label = phase_labels.get(action, action)

    lines.append(f"<b>━━━ 💡 추천 액션 ━━━</b>")
    lines.append(f"🟢 분할 매수 — {phase_label}")
    lines.append(f" • {reason}")
    lines.append(f" • 추천 비중: {weight_pct}%")

    if stop_loss > 0:
        loss_pct = abs((stop_loss - current_price) / current_price * 100)
        lines.append(f" • 손절가: {stop_loss:,}원 (-{loss_pct:.1f}%)")
    if target1 > 0:
        gain1_pct = (target1 - current_price) / current_price * 100
        lines.append(f" • 1차 목표: {target1:,}원 (+{gain1_pct:.1f}%)")
    if target2 > 0:
        gain2_pct = (target2 - current_price) / current_price * 100
        lines.append(f" • 2차 목표: {target2:,}원 (+{gain2_pct:.1f}%)")

    regime = details.get("regime", "")
    if regime:
        regime_kr = {"uptrend": "상승장", "downtrend": "하락장", "sideways": "횡보장"}.get(regime, regime)
        lines.append(f" • 시장 레짐: {regime_kr}")

    return "\n".join(lines)


def _build_signal_block(stock: dict) -> str:
    """단일 종목의 시그널 알림 블록을 생성한다 (리디자인)."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    signals = stock.get("signals", [])
    indicators = stock.get("indicators", {})
    investor = stock.get("investor", {})
    confluence_score = stock.get("confluence_score", 0)
    total_indicators = stock.get("total_indicators", 0)

    # 대표 시그널 타입 결정
    buy_signals = [s for s in signals if s.get("type") == "buy"]
    sell_signals = [s for s in signals if s.get("type") == "sell"]

    if buy_signals and not sell_signals:
        type_emoji = "📈"
        type_label = "매수 시그널"
    elif sell_signals and not buy_signals:
        type_emoji = "📉"
        type_label = "매도 시그널"
    else:
        type_emoji = "📊"
        type_label = "혼재 시그널"

    lines = []

    # 종목 헤더
    lines.append(DIVIDER)
    lines.append(f"{type_emoji} <b>{name} {type_label}</b>")
    price_str = _format_price(price)
    change_str = _format_change(change_pct)
    emoji = _change_emoji(change_pct)
    lines.append(f"{price_str}원 ({emoji}{change_str})")
    lines.append("")

    # 핵심 요약
    lines.append("<b>━━━ 핵심 요약 ━━━</b>")
    lines.append(_build_signal_summary_sentence(stock))
    lines.append("")

    # 시그널 근거 (✅/⬜ + 쉬운 해석)
    lines.append("<b>━━━ 시그널 근거 ━━━</b>")
    for sig in signals:
        trigger = sig.get("trigger", "")
        sig_type = sig.get("type", "")
        strength = sig.get("strength", 0)
        explain = _EASY_EXPLAIN.get(trigger, "")

        if sig_type == "buy":
            icon = "✅"
            score_str = f"+{strength:.2f}" if strength else ""
        elif sig_type == "sell":
            icon = "🔻"
            score_str = f"-{strength:.2f}" if strength else ""
        else:
            icon = "⬜"
            score_str = ""

        line = f"{icon} {trigger} {score_str}"
        if explain:
            line += f" — {explain}"
        lines.append(line)

    # 활성화되지 않은 주요 지표 (참고용)
    active_triggers = {sig.get("trigger", "") for sig in signals}
    inactive = []
    rsi = indicators.get("rsi")
    if rsi is not None and "RSI 과매도" not in active_triggers and "RSI 과매수" not in active_triggers:
        inactive.append(f"RSI {rsi:.0f} (중립)")
    macd_hist = indicators.get("macd_histogram")
    if macd_hist is not None and "MACD 매수" not in active_triggers and "MACD 매도" not in active_triggers:
        direction_str = "양" if macd_hist > 0 else "음"
        inactive.append(f"MACD {direction_str}전환")

    if inactive:
        lines.append(f"⬜ {' · '.join(inactive)}")

    lines.append("")

    # 합류 점수 + 프로그레스 바
    if total_indicators > 0:
        direction = stock.get("confluence_direction", "buy")
        label = _confluence_label(confluence_score, total_indicators, direction)
        bar = _progress_bar(confluence_score, total_indicators)
        lines.append("<b>━━━ 합류 점수 ━━━</b>")
        lines.append(f"{confluence_score:.1f} / {total_indicators} ({label})")
        lines.append(bar)
        lines.append("")

    # 참고 섹션 (손절, 뉴스, AI, 수급)
    ref_lines = []

    # 수급 정보
    foreign_net = investor.get("foreign_net")
    institutional_net = investor.get("institutional_net")
    foreign_consec = investor.get("foreign_consec_days", 0)
    institutional_consec = investor.get("institutional_consec_days", 0)

    if foreign_net is not None:
        amt_str = _format_shares(abs(foreign_net))
        if foreign_consec and foreign_consec >= 3:
            ref_lines.append(f"외인 {foreign_consec}일 연속 순매수 ({amt_str})")
        elif foreign_consec and foreign_consec <= -3:
            ref_lines.append(f"외인 {abs(foreign_consec)}일 연속 순매도 ({amt_str})")
        else:
            d = "순매수" if foreign_net >= 0 else "순매도"
            ref_lines.append(f"외인 {d} {amt_str}")

    if institutional_net is not None:
        amt_str = _format_shares(abs(institutional_net))
        if institutional_consec and institutional_consec >= 3:
            ref_lines.append(f"기관 {institutional_consec}일 연속 순매수 ({amt_str})")
        elif institutional_consec and institutional_consec <= -3:
            ref_lines.append(f"기관 {abs(institutional_consec)}일 연속 순매도 ({amt_str})")
        else:
            d = "순매수" if institutional_net >= 0 else "순매도"
            ref_lines.append(f"기관 {d} {amt_str}")

    # 손절 기준
    atr = indicators.get("atr")
    atr_stop_loss = indicators.get("atr_stop_loss")
    if atr is not None and atr_stop_loss is not None:
        ref_lines.append(f"손절 기준: ATR 기반 {atr_stop_loss:,}원")

    # 뉴스 감성
    news_sentiment = stock.get("news_sentiment")
    if news_sentiment is not None:
        sentiment = news_sentiment.get("sentiment", "중립")
        confidence = news_sentiment.get("confidence", 0.0)
        conf_pct = int(confidence * 100)
        if sentiment == "긍정":
            sent_emoji = "🟢"
        elif sentiment == "부정":
            sent_emoji = "🔴"
        else:
            sent_emoji = "⬜"
        ref_lines.append(f"뉴스 감성: {sent_emoji} {sentiment} (신뢰도 {conf_pct}%)")

        # 불일치 경고
        if signals:
            primary_type = signals[0]["type"]
            if (primary_type == "buy" and sentiment == "부정") or \
               (primary_type == "sell" and sentiment == "긍정"):
                ref_lines.append("⚠️ 뉴스 감성과 시그널 방향 불일치")

    # AI 판단
    llm = stock.get("llm_analysis")
    if llm:
        verdict = llm.get("verdict", "")
        conf = int(llm.get("confidence", 0) * 100)
        reasoning = llm.get("reasoning", "")
        risk_factors = llm.get("risk_factors", [])

        if verdict == "매수":
            v_emoji = "🟢"
        elif verdict == "매도":
            v_emoji = "🔴"
        else:
            v_emoji = "⬜"

        ref_lines.append(f"AI 판단: {v_emoji} {verdict} (신뢰도 {conf}%)")
        if reasoning:
            ref_lines.append(f"  → {reasoning}")
        if risk_factors:
            ref_lines.append(f"  ⚠️ {', '.join(risk_factors)}")

    if ref_lines:
        lines.append("<b>━━━ 참고 ━━━</b>")
        for rl in ref_lines:
            lines.append(f" • {rl}")

    # 매매 추천 액션
    rec = stock.get("trade_recommendation")
    if rec:
        lines.append("")
        lines.append(_build_recommendation_block(rec, price))

    return "\n".join(lines)


def _build_briefing_row(stock: dict) -> str:
    """일일 브리핑용 종목 한 줄 요약을 생성한다 (하위 호환)."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    signals = stock.get("signals", [])
    confluence_score = stock.get("confluence_score", 0)
    total_indicators = stock.get("total_indicators", 0)

    emoji = _change_emoji(change_pct)
    change_str = _format_change(change_pct)
    price_str = _format_price(price)

    # 시그널 요약
    buy_count = sum(1 for s in signals if s.get("type") == "buy")
    sell_count = sum(1 for s in signals if s.get("type") == "sell")
    if buy_count > 0 and sell_count == 0:
        signal_str = f"🟢 매수({buy_count})"
    elif sell_count > 0 and buy_count == 0:
        signal_str = f"🔴 매도({sell_count})"
    elif buy_count > 0 and sell_count > 0:
        signal_str = f"🟡 혼재"
    else:
        signal_str = "⬜ 없음"

    score_str = f"{confluence_score}/{total_indicators}" if total_indicators > 0 else "-"

    # 뉴스 감성 한줄 요약
    news_sentiment = stock.get("news_sentiment")
    news_str = ""
    if news_sentiment is not None:
        sentiment = news_sentiment.get("sentiment", "중립")
        if sentiment == "긍정":
            news_str = " | 뉴스 🟢"
        elif sentiment == "부정":
            news_str = " | 뉴스 🔴"
        else:
            news_str = " | 뉴스 ⬜"

    return (
        f"<b>{name}</b> ({ticker})\n"
        f"  {emoji} {price_str}원 ({change_str}) | {signal_str} | 합류 {score_str}{news_str}"
    )


# ──────────────────────────────────────────────
# 공개 함수
# ──────────────────────────────────────────────

def format_signal_alert(
    stock_data_list: List[dict],
    macro_data: Optional[dict] = None,
) -> str:
    """시그널 발생 시 전송하는 상세 알림 메시지를 생성한다.

    시그널이 있는 종목만 포함하며, 종목별로 핵심 요약, 시그널 근거,
    합류 점수 프로그레스 바, 참고 정보를 포함한 HTML 블록을 구성한다.
    매크로 이벤트(임계치 초과 변동)가 있으면 한 줄 요약을 상단에 추가한다.

    Args:
        stock_data_list: 각 종목의 시그널/지표 데이터 리스트.
                         signals 키가 비어 있는 종목은 제외된다.
        macro_data: 글로벌 매크로 지표 dict (없으면 None).

    Returns:
        텔레그램 parse_mode="HTML" 형식의 메시지 문자열.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"<b>📡 Signalight 매매 시그널</b>")
    lines.append(now_str)

    # 매크로 이벤트 한 줄 요약 (임계치 초과 지표만)
    if macro_data:
        alert_items = [
            item for item in macro_data.values()
            if isinstance(item, dict)
            and item.get("change_pct") is not None
            and abs(item["change_pct"]) >= _MACRO_ALERT_THRESHOLD
        ]
        if alert_items:
            parts = []
            for item in alert_items:
                name = item.get("name", "")
                change_pct = item["change_pct"]
                parts.append(f"{name} {_format_change(change_pct)}")
            lines.append(f"🌍 매크로 이벤트: {' · '.join(parts)}")

    # 시그널 있는 종목만 필터
    signal_stocks = [s for s in stock_data_list if s.get("signals")]

    if not signal_stocks:
        lines.append("")
        lines.append("현재 발생한 시그널이 없습니다.")
        return "\n".join(lines)

    # 시그널 요약 (상단)
    buy_names = [s["name"] for s in signal_stocks
                 if any(sig.get("type") == "buy" for sig in s.get("signals", []))]
    sell_names = [s["name"] for s in signal_stocks
                  if any(sig.get("type") == "sell" for sig in s.get("signals", []))]

    lines.append("")
    summary_parts = []
    if buy_names:
        summary_parts.append(f"🟢 매수: {', '.join(buy_names)}")
    if sell_names:
        summary_parts.append(f"🔴 매도: {', '.join(sell_names)}")
    lines.append(" | ".join(summary_parts))

    for stock in signal_stocks:
        lines.append("")
        lines.append(_build_signal_block(stock))

    return "\n".join(lines)


def format_daily_briefing(
    stock_data_list: List[dict],
    macro_data: Optional[dict] = None,
) -> str:
    """장마감 일일 요약 메시지를 생성한다.

    시장 온도, 글로벌 매크로 (있을 때), 주목 종목 (시그널 있는 종목 상세),
    나머지 종목 compact, 한줄 코멘트로 구성된 분석 보고서 스타일의 메시지.

    Args:
        stock_data_list: 전체 감시 종목 데이터 리스트.
        macro_data: 글로벌 매크로 지표 dict (없으면 None, 섹션 생략).

    Returns:
        텔레그램 parse_mode="HTML" 형식의 메시지 문자열.
    """
    now = datetime.now()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    day_name = weekday_kr[now.weekday()]
    today_str = now.strftime("%Y-%m-%d")

    lines = []
    lines.append(f"<b>📊 Signalight 일일 브리핑</b>")
    lines.append(f"{today_str} ({day_name}) 장마감")
    lines.append("")

    # 글로벌 매크로 (데이터가 있을 때만)
    macro_section = _build_macro_section(macro_data)
    if macro_section:
        lines.append(macro_section)
        lines.append("")

    if not stock_data_list:
        lines.append("감시 종목 데이터가 없습니다.")
        return "\n".join(lines)

    # 시장 온도
    lines.append(_build_market_temperature(stock_data_list))
    lines.append("")

    # 주목 종목 (시그널 있는 종목)
    spotlight_stocks = [s for s in stock_data_list if s.get("signals")]
    other_stocks = [s for s in stock_data_list if not s.get("signals")]

    if spotlight_stocks:
        lines.append(f"<b>━━━ 🔥 주목 종목 ━━━</b>")
        lines.append("")
        for stock in spotlight_stocks:
            lines.append(_build_spotlight_block(stock))
            lines.append("")

    # 나머지 종목 (compact)
    if other_stocks:
        lines.append(f"<b>━━━ 나머지 종목 ━━━</b>")
        for stock in other_stocks:
            lines.append(_build_compact_row(stock))
        lines.append("")

    # 한줄 코멘트
    lines.append(_build_market_comment(stock_data_list))

    return "\n".join(lines)


def format_weekly_report(
    stock_data_list: List[dict],
    weekly_signals: List[dict],
) -> str:
    """주간 등락률 및 시그널 요약 리포트를 생성한다.

    Args:
        stock_data_list: 주간 종료 시점 기준 종목 데이터 리스트.
                         각 항목에 "weekly_change_pct" 키가 있으면
                         주간 등락률로 사용한다. 없으면 "change_pct" 사용.
        weekly_signals: 주간 발생 시그널 목록.
                        {"name", "ticker", "date", "trigger", "type"} 구조.

    Returns:
        텔레그램 parse_mode="HTML" 형식의 메시지 문자열.
    """
    now = datetime.now()
    # 주 시작일(월요일) 계산
    week_start = now.strftime("%m/%d")  # 간단히 현재 날짜 기준으로 표시
    week_label = now.strftime("%Y년 %m월 %W주차")

    lines = []
    lines.append(f"<b>📋 Signalight 주간 리포트</b>")
    lines.append(week_label)
    lines.append("")
    lines.append(DIVIDER)
    lines.append("<b>[종목별 주간 등락률]</b>")
    lines.append("")

    if stock_data_list:
        for stock in stock_data_list:
            name = stock.get("name", "")
            ticker = stock.get("ticker", "")
            price = stock.get("price", 0)
            # 주간 등락률 우선, 없으면 일간 등락률 사용
            change_pct = stock.get("weekly_change_pct", stock.get("change_pct", 0.0))
            emoji = _change_emoji(change_pct)
            change_str = _format_change(change_pct)
            price_str = _format_price(price)
            lines.append(f"{emoji} <b>{name}</b> ({ticker})  {change_str}  {price_str}원")
    else:
        lines.append("종목 데이터가 없습니다.")

    # 주간 시그널 요약
    lines.append("")
    lines.append(DIVIDER)
    lines.append("<b>[주간 시그널 발생 내역]</b>")
    lines.append("")

    if weekly_signals:
        buy_signals = [s for s in weekly_signals if s.get("type") == "buy"]
        sell_signals = [s for s in weekly_signals if s.get("type") == "sell"]

        if buy_signals:
            lines.append("🟢 <b>매수 시그널</b>")
            for sig in buy_signals:
                date_str = sig.get("date", "")
                name = sig.get("name", sig.get("ticker", ""))
                trigger = sig.get("trigger", "")
                lines.append(f" • [{date_str}] {name}: {trigger}")
            lines.append("")

        if sell_signals:
            lines.append("🔴 <b>매도 시그널</b>")
            for sig in sell_signals:
                date_str = sig.get("date", "")
                name = sig.get("name", sig.get("ticker", ""))
                trigger = sig.get("trigger", "")
                lines.append(f" • [{date_str}] {name}: {trigger}")
            lines.append("")
    else:
        lines.append("이번 주 발생한 시그널이 없습니다.")
        lines.append("")

    # 주간 통계
    total_buy = sum(1 for s in weekly_signals if s.get("type") == "buy")
    total_sell = sum(1 for s in weekly_signals if s.get("type") == "sell")
    lines.append(DIVIDER)
    lines.append(f"총 시그널: 매수 {total_buy}건 / 매도 {total_sell}건")

    return "\n".join(lines)
