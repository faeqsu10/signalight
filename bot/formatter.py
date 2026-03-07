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


def _confluence_label(score: int, total: int) -> str:
    """합류 점수를 텍스트로 변환한다."""
    if total == 0:
        return "데이터 없음"
    ratio = score / total
    if ratio >= 0.8:
        return "강한 매수" if score > 0 else "강한 매도"
    elif ratio >= 0.6:
        return "매수 우세" if score > 0 else "매도 우세"
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


DIVIDER = "━━━━━━━━━━━━━━━━━━━"


# ──────────────────────────────────────────────
# 내부 블록 빌더
# ──────────────────────────────────────────────

def _build_signal_block(stock: dict) -> str:
    """단일 종목의 시그널 알림 블록을 생성한다."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    signals: List[dict] = stock.get("signals", [])
    indicators: dict = stock.get("indicators", {})
    investor: dict = stock.get("investor", {})
    confluence_score = stock.get("confluence_score", 0)
    total_indicators = stock.get("total_indicators", 0)

    # 대표 시그널 타입 결정 (첫 번째 시그널 기준)
    primary_signal_type = signals[0]["type"] if signals else "hold"

    lines = []

    # 종목 헤더
    lines.append(DIVIDER)
    lines.append(f"<b>{name}</b> ({ticker}) | {_signal_emoji(primary_signal_type)}")
    lines.append(DIVIDER)

    # 현재가
    price_str = _format_price(price)
    change_str = _format_change(change_pct)
    emoji = _change_emoji(change_pct)
    lines.append(f"현재가: {price_str}원 {emoji} ({change_str})")
    lines.append("")

    # 트리거 시그널
    for sig in signals:
        trigger = sig.get("trigger", "")
        detail = sig.get("detail", "")
        lines.append(f"[트리거] {trigger}")
        if detail:
            lines.append(f" • {detail}")
    lines.append("")

    # 보조 지표
    lines.append("[보조 지표]")

    rsi = indicators.get("rsi")
    if rsi is not None:
        lines.append(f" • RSI: {rsi:.1f} ({_rsi_label(rsi)})")

    macd_hist = indicators.get("macd_histogram")
    if macd_hist is not None:
        if macd_hist > 0:
            lines.append(f" • MACD: 히스토그램 양전환 (+{macd_hist:.1f})")
        elif macd_hist < 0:
            lines.append(f" • MACD: 히스토그램 음전환 ({macd_hist:.1f})")
        else:
            lines.append(f" • MACD: 히스토그램 0")

    volume_ratio = indicators.get("volume_ratio")
    if volume_ratio is not None:
        pct = int(volume_ratio * 100)
        lines.append(f" • 거래량: 평균 대비 {pct}%")

    vix = indicators.get("vix")
    if vix is not None:
        lines.append(f" • VIX: {vix:.1f} ({_vix_label(vix)})")

    lines.append("")

    # 수급 정보
    foreign_net = investor.get("foreign_net")
    institutional_net = investor.get("institutional_net")
    foreign_consec = investor.get("foreign_consec_days", 0)
    institutional_consec = investor.get("institutional_consec_days", 0)

    has_investor = any(v is not None for v in [foreign_net, institutional_net])
    if has_investor:
        lines.append("[수급]")
        if foreign_net is not None:
            amt_str = _format_shares(abs(foreign_net))
            if foreign_consec and foreign_consec > 0:
                lines.append(f" • 외인 {foreign_consec}일 연속 순매수 ({amt_str})")
            elif foreign_consec and foreign_consec < 0:
                lines.append(f" • 외인 {abs(foreign_consec)}일 연속 순매도 ({amt_str})")
            else:
                direction = "순매수" if foreign_net >= 0 else "순매도"
                lines.append(f" • 외인 {direction}: {amt_str}")

        if institutional_net is not None:
            amt_str = _format_shares(abs(institutional_net))
            if institutional_consec and institutional_consec > 0:
                lines.append(f" • 기관 {institutional_consec}일 연속 순매수 ({amt_str})")
            elif institutional_consec and institutional_consec < 0:
                lines.append(f" • 기관 {abs(institutional_consec)}일 연속 순매도 ({amt_str})")
            else:
                direction = "순매수" if institutional_net >= 0 else "순매도"
                lines.append(f" • 기관 {direction}: {amt_str}")

        lines.append("")

    # 합류 점수
    if total_indicators > 0:
        label = _confluence_label(confluence_score, total_indicators)
        lines.append(f"[합류 점수] {confluence_score}/{total_indicators} ({label})")

    return "\n".join(lines)


def _build_briefing_row(stock: dict) -> str:
    """일일 브리핑용 종목 한 줄 요약을 생성한다."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0.0)
    signals: List[dict] = stock.get("signals", [])
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

    return (
        f"<b>{name}</b> ({ticker})\n"
        f"  {emoji} {price_str}원 ({change_str}) | {signal_str} | 합류 {score_str}"
    )


# ──────────────────────────────────────────────
# 공개 함수
# ──────────────────────────────────────────────

def format_signal_alert(stock_data_list: List[dict]) -> str:
    """시그널 발생 시 전송하는 상세 알림 메시지를 생성한다.

    시그널이 있는 종목만 포함하며, 종목별로 트리거, 보조 지표, 수급,
    합류 점수를 포함한 HTML 블록을 구성한다.

    Args:
        stock_data_list: 각 종목의 시그널/지표 데이터 리스트.
                         signals 키가 비어 있는 종목은 제외된다.

    Returns:
        텔레그램 parse_mode="HTML" 형식의 메시지 문자열.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"<b>Signalight 매매 시그널</b>")
    lines.append(now_str)

    # 시그널 있는 종목만 필터
    signal_stocks = [s for s in stock_data_list if s.get("signals")]

    if not signal_stocks:
        lines.append("")
        lines.append("현재 발생한 시그널이 없습니다.")
        return "\n".join(lines)

    for stock in signal_stocks:
        lines.append("")
        lines.append(_build_signal_block(stock))

    return "\n".join(lines)


def format_daily_briefing(stock_data_list: List[dict]) -> str:
    """장마감 일일 요약 메시지를 생성한다.

    시그널 유무와 관계없이 전체 감시 종목의 등락률, 시그널 현황,
    합류 점수를 요약한다.

    Args:
        stock_data_list: 전체 감시 종목 데이터 리스트.

    Returns:
        텔레그램 parse_mode="HTML" 형식의 메시지 문자열.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"<b>Signalight 일일 브리핑</b>")
    lines.append(f"{today_str} 장마감")
    lines.append("")
    lines.append(DIVIDER)

    if not stock_data_list:
        lines.append("감시 종목 데이터가 없습니다.")
        return "\n".join(lines)

    for stock in stock_data_list:
        lines.append(_build_briefing_row(stock))
        lines.append("")

    # 시그널 발생 종목 집계
    buy_stocks = [
        s["name"] for s in stock_data_list
        if any(sig.get("type") == "buy" for sig in s.get("signals", []))
    ]
    sell_stocks = [
        s["name"] for s in stock_data_list
        if any(sig.get("type") == "sell" for sig in s.get("signals", []))
    ]

    lines.append(DIVIDER)
    lines.append("<b>[오늘의 시그널 요약]</b>")
    if buy_stocks:
        lines.append(f"🟢 매수: {', '.join(buy_stocks)}")
    if sell_stocks:
        lines.append(f"🔴 매도: {', '.join(sell_stocks)}")
    if not buy_stocks and not sell_stocks:
        lines.append("⬜ 발생 시그널 없음")

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
    lines.append(f"<b>Signalight 주간 리포트</b>")
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
