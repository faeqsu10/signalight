"""미국 주식 자율매매 텔레그램 명령어 핸들러.

기존 bot/interactive.py의 polling 루프에서 호출된다.
AUTO_TRADE_CHAT_ID에서 수신된 us_ 접두사 명령어만 처리한다.

명령어:
    /us_status    — 🇺🇸 US 자율매매 상태 (Alpaca 계좌 잔고, 포지션, MDD)
    /us_scan      — 🇺🇸 US 유니버스 즉시 스캔 (현재 후보 종목 표시)
    /us_positions — 🇺🇸 US 보유 포지션 상세 (Alpaca API에서 실시간)
    /us_config    — 🇺🇸 US 자율매매 설정값 표시
"""

import logging
import os
from typing import Optional

from bot.telegram import send_message
from autonomous.us.config import US_AUTO_CONFIG

logger = logging.getLogger("signalight.us")


def handle_us_status(chat_id: str) -> None:
    """공개 래퍼: /us_status."""
    _cmd_us_status(chat_id)


def handle_us_scan(chat_id: str) -> None:
    """공개 래퍼: /us_scan."""
    _cmd_us_scan(chat_id)


def handle_us_positions(chat_id: str) -> None:
    """공개 래퍼: /us_positions."""
    _cmd_us_positions(chat_id)


def handle_us_config(chat_id: str) -> None:
    """공개 래퍼: /us_config."""
    _cmd_us_config(chat_id)


def handle_us_command(chat_id: str, command: str, args: str) -> bool:
    """US 자율매매 명령어를 처리한다.

    Returns:
        True = 처리 완료, False = 해당 명령어 아님
    """
    handlers = {
        "us_status": _cmd_us_status,
        "us_scan": _cmd_us_scan,
        "us_positions": _cmd_us_positions,
        "us_config": _cmd_us_config,
    }

    handler = handlers.get(command)
    if handler:
        handler(chat_id)
        return True
    return False


def _cmd_us_status(chat_id: str) -> None:
    """/us_status — Alpaca 계좌 잔고 + 보유 포지션 + MDD."""
    try:
        from trading.alpaca_client import AlpacaClient
        client = AlpacaClient()
        acct = client.get_account()
        positions = client.get_positions()
    except Exception as e:
        logger.error("Alpaca 계좌 조회 실패: %s", e)
        send_message(f"🇺🇸 [US 자율매매] 계좌 조회 실패: {e}", chat_id=chat_id)
        return

    kill_active = os.path.exists(US_AUTO_CONFIG.kill_switch_path)
    mode = "Paper Trading" if not US_AUTO_CONFIG.dry_run else "Dry Run"

    equity = float(acct.get("equity", 0))
    cash = float(acct.get("cash", 0))
    buying_power = float(acct.get("buying_power", 0))
    portfolio_value = float(acct.get("portfolio_value", equity))
    initial = US_AUTO_CONFIG.virtual_asset
    pnl_pct = ((portfolio_value - initial) / initial * 100) if initial > 0 else 0.0

    lines = [
        "🇺🇸 <b>[US 자율매매] 상태</b>",
        f"모드: {mode}",
        "",
    ]

    if kill_active:
        lines.append("⛔ 킬스위치: <b>활성</b> (매매 중단)")
    else:
        lines.append("✅ 매매 상태: 정상")

    lines.append("")
    lines.append("<b>▸ Alpaca 계좌</b>")
    lines.append(f"  포트폴리오 가치: ${portfolio_value:,.2f}")
    lines.append(f"  현금: ${cash:,.2f}")
    lines.append(f"  매수 가능: ${buying_power:,.2f}")
    lines.append(f"  총 수익률: {pnl_pct:+.2f}%")

    lines.append(f"\n<b>▸ 보유</b>: {len(positions)}종목")
    if positions:
        for pos in positions[:5]:
            symbol = pos.get("symbol", "")
            qty = float(pos.get("qty", 0))
            unrealized_pct = float(pos.get("unrealized_plpc", 0)) * 100
            lines.append(f"  {symbol} {qty:.2f}주 ({unrealized_pct:+.1f}%)")
        if len(positions) > 5:
            lines.append(f"  ... 외 {len(positions) - 5}종목")

    lines.append(f"\n<b>▸ 리스크 한도</b>")
    lines.append(f"  최대 동시 포지션: {US_AUTO_CONFIG.max_positions}종목")
    lines.append(f"  최대 낙폭 한도: {US_AUTO_CONFIG.max_drawdown_pct:.1f}%")
    lines.append(f"  일일 손실 한도: {US_AUTO_CONFIG.daily_loss_limit_pct:.1f}%")

    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_us_scan(chat_id: str) -> None:
    """/us_scan — US 유니버스 즉시 스캔."""
    import threading

    send_message("🇺🇸 US 유니버스 스캔을 시작합니다. 잠시 후 결과를 전송합니다...", chat_id=chat_id)
    logger.info("/us_scan 명령: 수동 US 유니버스 스캔 요청")

    scan_thread = threading.Thread(
        target=_run_us_scan,
        args=(chat_id,),
        name="us-manual-scan",
        daemon=True,
    )
    scan_thread.start()


def _run_us_scan(chat_id: str) -> None:
    """US 유니버스 스캔을 실행하고 결과를 전송한다."""
    try:
        from autonomous.us.universe import USUniverseSelector

        selector = USUniverseSelector()
        candidates = selector.select_universe()

        if not candidates:
            send_message("🇺🇸 [US 스캔] 현재 매매 후보 종목이 없습니다.", chat_id=chat_id)
            return

        signal_labels = {
            "golden_cross": "골든크로스",
            "rsi_oversold": "RSI과매도",
            "volume_surge": "거래량급증",
            "near_golden_cross": "근접골든크로스",
        }

        lines = [
            f"🇺🇸 <b>[US 스캔] 매매 후보 ({len(candidates)}종목)</b>",
            "",
        ]

        for i, c in enumerate(candidates, 1):
            ticker = c["ticker"]
            name = c.get("name", ticker)
            price = c.get("price", 0)
            score = c.get("composite_score", 0)
            signals = c.get("scan_signals", [])
            sig_labels = [signal_labels.get(s, s) for s in signals]

            lines.append(f"<b>{i}. {name} ({ticker})</b>")
            lines.append(f"  가격: ${price:,.2f} | 점수: {score:.1f}")
            if sig_labels:
                lines.append(f"  시그널: {', '.join(sig_labels)}")

            # 추가 정보
            if c.get("rsi") is not None:
                lines.append(f"  RSI: {c['rsi']:.1f}")
            if c.get("volume_ratio") is not None:
                lines.append(f"  거래량 비율: {c['volume_ratio']:.1f}x")
            lines.append("")

        send_message("\n".join(lines), chat_id=chat_id)

    except Exception as e:
        logger.error("US 수동 스캔 오류: %s", e)
        send_message(f"🇺🇸 [US 스캔] 오류: {e}", chat_id=chat_id)


def _cmd_us_positions(chat_id: str) -> None:
    """/us_positions — Alpaca 실시간 보유 포지션 상세."""
    try:
        from trading.alpaca_client import AlpacaClient
        client = AlpacaClient()
        positions = client.get_positions()
    except Exception as e:
        logger.error("Alpaca 포지션 조회 실패: %s", e)
        send_message(f"🇺🇸 [US 포지션] 조회 실패: {e}", chat_id=chat_id)
        return

    if not positions:
        send_message("🇺🇸 현재 보유 중인 US 포지션이 없습니다.", chat_id=chat_id)
        return

    lines = [
        f"🇺🇸 <b>[US 포지션] 보유 종목 ({len(positions)}개)</b>",
        "",
    ]

    for pos in positions:
        symbol = pos.get("symbol", "")
        qty = float(pos.get("qty", 0))
        avg_entry = float(pos.get("avg_entry_price", 0))
        current_price = float(pos.get("current_price", 0))
        market_value = float(pos.get("market_value", 0))
        unrealized_pl = float(pos.get("unrealized_pl", 0))
        unrealized_pct = float(pos.get("unrealized_plpc", 0)) * 100
        side = pos.get("side", "long")

        pl_emoji = "🟢" if unrealized_pl >= 0 else "🔴"
        side_label = "롱" if side == "long" else "숏"

        lines.append(f"<b>{symbol}</b> ({side_label})")
        lines.append(f"  수량: {qty:.4f}주")
        lines.append(f"  진입가: ${avg_entry:,.2f}")
        lines.append(f"  현재가: ${current_price:,.2f}")
        lines.append(f"  시장가치: ${market_value:,.2f}")
        lines.append(f"  평가손익: {pl_emoji} ${unrealized_pl:+,.2f} ({unrealized_pct:+.1f}%)")
        lines.append("")

    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_us_config(chat_id: str) -> None:
    """/us_config — US 자율매매 설정 + 기본값 비교 + 개선 루프 상태."""
    cfg = US_AUTO_CONFIG
    mode = "Paper Trading" if not cfg.dry_run else "Dry Run"

    # 기본값 (USAutonomousConfig 디폴트)
    from autonomous.us.config import USAutonomousConfig
    defaults = USAutonomousConfig()

    mode_label = getattr(cfg, "bot_label", "") or "US"

    lines = [
        f"<b>[{mode_label}] 설정 현황</b>",
        f"모드: {mode}",
        "",
        "<b>▸ 진입 임계값</b> (현재 ← 기본값)",
        f"  상승장: {cfg.initial_entry_threshold_uptrend} ← {defaults.initial_entry_threshold_uptrend}",
        f"  횡보장: {cfg.initial_entry_threshold_sideways} ← {defaults.initial_entry_threshold_sideways}",
        f"  하락장: {cfg.initial_entry_threshold_downtrend} ← {defaults.initial_entry_threshold_downtrend}",
        "",
        "<b>▸ 지표 설정</b>",
        f"  사용 지표: {', '.join(cfg.enabled_indicators) if cfg.enabled_indicators else '전체'}",
        f"  RSI 매수: {cfg.indicator_rsi_oversold} ← {defaults.indicator_rsi_oversold}",
        f"  RSI 스캔: {cfg.scan_rsi_oversold_threshold} ← {defaults.scan_rsi_oversold_threshold}",
    ]

    if cfg.fixed_target_pct > 0:
        lines.append(f"  고정 목표: +{cfg.fixed_target_pct}%")
    if cfg.skip_trend_gate:
        lines.append("  추세 게이트: 스킵")

    lines += [
        "",
        "<b>▸ 포지션 관리</b> (현재 ← 기본값)",
        f"  종목 비중: {cfg.target_weight_pct:.1f}% ← {defaults.target_weight_pct:.1f}%",
        f"  최대 포지션: {cfg.max_positions}종목 ← {defaults.max_positions}종목",
        f"  섹터 한도: {cfg.max_sector_positions}종목 ← {defaults.max_sector_positions}종목",
        f"  최대 손절: {cfg.max_loss_pct:.1f}%",
        f"  최대 보유: {cfg.max_holding_days}일",
        "",
        "<b>▸ 서킷 브레이커</b>",
        f"  일일 손실: {cfg.daily_loss_limit_pct:.1f}% / 주간: {cfg.weekly_loss_limit_pct:.1f}%",
        f"  연속 패배: {cfg.max_consecutive_losses}연패 / MDD: {cfg.max_drawdown_pct:.1f}%",
        "",
        "<b>▸ 개선 루프</b>",
        f"  상태: ⏳ 데이터 수집 중",
        f"  주기: 매주 {cfg.evaluation_day} {cfg.evaluation_time} ET",
        f"  현재 설정은 공격적 초기값 — 거래 데이터 축적 후 자동 최적화",
        "",
        "<b>▸ 실행 타이밍 (ET)</b>",
        f"  장 시작: {cfg.market_open_hour:02d}:{cfg.market_open_minute:02d} ET",
        f"  장 마감: {cfg.market_close_hour:02d}:{cfg.market_close_minute:02d} ET",
        f"  모니터링: {cfg.monitor_interval_min}분 간격",
    ]

    send_message("\n".join(lines), chat_id=chat_id)
