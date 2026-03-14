"""자율매매 텔레그램 인터랙티브 명령어 핸들러.

기존 bot/interactive.py의 polling 루프에서 호출된다.
AUTO_TRADE_CHAT_ID에서 수신된 명령어만 처리한다.

명령어:
    /help     — 자율매매 명령어 목록
    /status   — 보유 종목 + PnL + 서킷브레이커 상태
    /report   — 성과 리포트 즉시 발송
    /pause    — 자율매매 일시 정지 (킬스위치 ON)
    /resume   — 자율매매 재개 (킬스위치 OFF)
    /history  — 최근 매매 이력
    /positions — 보유 종목 상세
"""

import logging
import os
from datetime import date
from typing import Optional

from bot.telegram import send_message
from autonomous.config import AUTO_CONFIG
from autonomous.state import PipelineState
from trading.position_tracker import PositionTracker

logger = logging.getLogger("signalight.auto")

_state = PipelineState()
_tracker = PositionTracker()


def is_auto_trade_chat(chat_id: str) -> bool:
    """자율매매 전용 채팅인지 확인한다."""
    auto_id = AUTO_CONFIG.auto_trade_chat_id
    return bool(auto_id) and str(chat_id) == str(auto_id)


def handle_auto_command(chat_id: str, command: str, args: str) -> bool:
    """자율매매 명령어를 처리한다.

    Returns:
        True = 처리 완료, False = 해당 명령어 아님
    """
    handlers = {
        "help": _cmd_help,
        "status": _cmd_status,
        "config": _cmd_config,
        "report": _cmd_report,
        "pause": _cmd_pause,
        "resume": _cmd_resume,
        "history": _cmd_history,
        "positions": _cmd_positions,
    }

    handler = handlers.get(command)
    if handler:
        handler(chat_id)
        return True
    return False


def _cmd_help(chat_id: str) -> None:
    """/help — 자율매매 명령어 목록."""
    mode = "시뮬레이션" if AUTO_CONFIG.dry_run else "실전"
    lines = [
        "<b>[자율매매] 명령어</b>",
        "",
        "/status — 현재 상태 요약",
        "/config — 현재 설정 및 옵티마이저 상태",
        "/positions — 보유 종목 상세",
        "/history — 최근 매매 이력",
        "/report — 성과 리포트 발송",
        "/pause — 자율매매 일시 정지",
        "/resume — 자율매매 재개",
        "",
        f"<i>모드: {mode}</i>",
    ]
    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_status(chat_id: str) -> None:
    """/status — 보유 종목 + PnL + 서킷브레이커 상태."""
    open_positions = _tracker.get_all_open()
    today = date.today().isoformat()
    daily = _state.get_daily_pnl(today)
    weekly = _state.get_weekly_pnl()
    cb = _state.is_circuit_breaker_active()
    consecutive = _state.get_consecutive_losses()
    max_dd = _state.get_max_drawdown()

    # 킬스위치 상태
    kill_active = os.path.exists(AUTO_CONFIG.kill_switch_path)

    mode = "시뮬레이션" if AUTO_CONFIG.dry_run else "실전"
    env = "모의투자" if AUTO_CONFIG.use_mock else "실전투자"

    lines = [
        "<b>[자율매매] 상태</b>",
        f"모드: {mode} ({env})",
        "",
    ]

    # 킬스위치 / 서킷브레이커
    if kill_active:
        lines.append("⛔ 킬스위치: <b>활성</b> (매매 중단)")
    elif cb:
        lines.append(f"⚠️ 서킷브레이커: <b>활성</b> ({cb['trigger_type']})")
    else:
        lines.append("✅ 매매 상태: 정상")

    lines.append("")

    # 오늘 PnL
    if daily:
        lines.append("<b>▸ 오늘</b>")
        lines.append(f"  거래: {daily['trades_count']}건 "
                      f"(승 {daily['wins']} / 패 {daily['losses']})")
        lines.append(f"  PnL: {daily['realized_pnl']:+,}원")
    else:
        lines.append("<b>▸ 오늘</b>: 거래 없음")

    # 주간 PnL
    lines.append(f"\n<b>▸ 주간</b>")
    lines.append(f"  거래: {weekly['total_trades']}건 "
                  f"(승 {weekly['total_wins']} / 패 {weekly['total_losses']})")
    lines.append(f"  PnL: {weekly['total_pnl']:+,}원")

    # 리스크
    lines.append(f"\n<b>▸ 리스크</b>")
    lines.append(f"  연속 패배: {consecutive}연패 / {AUTO_CONFIG.max_consecutive_losses}연패 한도")
    lines.append(f"  최대 낙폭: {max_dd:.1f}% / {AUTO_CONFIG.max_drawdown_pct:.1f}% 한도")

    # 보유 요약
    lines.append(f"\n<b>▸ 보유</b>: {len(open_positions)}종목")
    if open_positions:
        for pos in open_positions[:5]:
            lines.append(f"  {pos['name']}({pos['ticker']}) "
                          f"진입 {pos['entry_price']:,}원")
        if len(open_positions) > 5:
            lines.append(f"  ... 외 {len(open_positions) - 5}종목")

    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_report(chat_id: str) -> None:
    """/report — 성과 리포트 즉시 발송."""
    from autonomous.evaluator import PerformanceEvaluator

    send_message("성과 리포트를 생성합니다...", chat_id=chat_id)
    evaluator = PerformanceEvaluator(state=_state, position_tracker=_tracker)
    evaluator.weekly_report()


def _cmd_pause(chat_id: str) -> None:
    """/pause — 킬스위치 ON (매매 중단)."""
    try:
        with open(AUTO_CONFIG.kill_switch_path, "w") as f:
            f.write(f"paused by telegram command at {date.today().isoformat()}\n")
        logger.warning("자율매매 일시 정지 (킬스위치 ON)")
        send_message(
            "⛔ <b>자율매매 일시 정지</b>\n"
            "킬스위치가 활성화되었습니다.\n"
            "매수/매도 주문이 중단됩니다.\n\n"
            "/resume 으로 재개할 수 있습니다.",
            chat_id=chat_id,
        )
    except OSError as e:
        logger.error("킬스위치 파일 생성 실패: %s", e)
        send_message(f"킬스위치 활성화 실패: {e}", chat_id=chat_id)


def _cmd_resume(chat_id: str) -> None:
    """/resume — 킬스위치 OFF (매매 재개)."""
    path = AUTO_CONFIG.kill_switch_path
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.info("자율매매 재개 (킬스위치 OFF)")
            send_message(
                "✅ <b>자율매매 재개</b>\n"
                "킬스위치가 해제되었습니다.\n"
                "매매가 다시 활성화됩니다.",
                chat_id=chat_id,
            )
        except OSError as e:
            logger.error("킬스위치 파일 삭제 실패: %s", e)
            send_message(f"킬스위치 해제 실패: {e}", chat_id=chat_id)
    else:
        send_message("킬스위치가 이미 비활성 상태입니다.", chat_id=chat_id)


def _cmd_history(chat_id: str) -> None:
    """/history — 최근 매매 이력."""
    trades = _state.get_recent_trades(days=14)

    if not trades:
        send_message("최근 14일 매매 이력이 없습니다.", chat_id=chat_id)
        return

    lines = [
        f"<b>[자율매매] 최근 거래 ({len(trades)}건)</b>",
        "",
    ]

    for trade in trades[:15]:
        side_emoji = "🟢" if trade["side"] == "buy" else "🔴"
        side_kr = "매수" if trade["side"] == "buy" else "매도"

        pnl_str = ""
        if trade.get("pnl_pct") is not None:
            pnl_str = f" ({trade['pnl_pct']:+.1f}%)"

        lines.append(
            f"{side_emoji} {trade['trade_date']} {side_kr} "
            f"{trade['name']} {trade['quantity']}주 "
            f"@ {trade['price']:,}원{pnl_str}"
        )

    # 성과 요약
    perf = _state.get_performance_summary(days=14)
    if perf["total_trades"] > 0:
        lines.append("")
        lines.append(f"승률: {perf['win_rate']}% "
                      f"| 평균 PnL: {perf['avg_pnl_pct']:+.2f}%")

    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_config(chat_id: str) -> None:
    """/config — 현재 설정 + 기본값 비교 + 개선 루프 상태."""
    from autonomous.optimizer import StrategyOptimizer

    opt = StrategyOptimizer(state=_state)
    params = opt.get_optimized_params()

    cfg = AUTO_CONFIG

    # 기본값 (AutonomousConfig 디폴트)
    from autonomous.config import AutonomousConfig
    defaults = AutonomousConfig()

    mode_label = cfg.bot_label or cfg.bot_mode
    lines = [
        f"<b>[{mode_label}] 설정 현황</b>",
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
        "<b>▸ 스캔 가중치</b>",
        f"  골든크로스: {params['scan_weights']['golden_cross']}",
        f"  RSI과매도: {params['scan_weights']['rsi_oversold']}",
        f"  거래량급증: {params['scan_weights']['volume_surge']}",
        "",
        "<b>▸ 개선 루프 (옵티마이저)</b>",
    ]

    if params["active"]:
        lines.append(
            f"  상태: ✅ 활성 (총 {params['total_trades']}건, "
            f"승률 {params['overall_win_rate']:.0f}%)"
        )
        lines.append(f"  WF 통과: {params['wf_passes']}/{params['wf_valid_folds']} folds")
        lines.append(f"  Sharpe 개선: {params['avg_improvement']:+.3f}")
        # 기본값 대비 변경
        d_thresh = params.get("default_buy_thresholds", {})
        c_thresh = params.get("buy_thresholds", {})
        if d_thresh != c_thresh:
            lines.append("  조정된 임계값:")
            for regime in ("uptrend", "sideways", "downtrend"):
                d = d_thresh.get(regime, "?")
                c = c_thresh.get(regime, "?")
                label = {"uptrend": "상승", "sideways": "횡보", "downtrend": "하락"}[regime]
                lines.append(f"    {label}: {d} → {c}")
    else:
        total = params["total_trades"]
        min_t = params["min_trades"]
        lines.append(
            f"  상태: ⏳ 대기 (거래 {total}/{min_t}건)"
        )
        lines.append(f"  조건: {min_t}건 거래 후 자동 최적화 시작")
        lines.append(f"  주기: 매주 {cfg.evaluation_day} {cfg.evaluation_time}")

    # 마지막 최적화 이력
    latest = params.get("latest_change")
    if latest:
        applied = "적용" if latest.get("applied") else "유지"
        lines.append(f"\n  마지막 판단: {latest.get('evaluated_at', '?')} ({applied})")
        reason = latest.get("reason", "")
        if reason:
            lines.append(f"  사유: {reason[:80]}")

    send_message("\n".join(lines), chat_id=chat_id)


def _cmd_positions(chat_id: str) -> None:
    """/positions — 보유 종목 상세."""
    positions = _tracker.get_all_open()

    if not positions:
        send_message("현재 보유 중인 종목이 없습니다.", chat_id=chat_id)
        return

    lines = [
        f"<b>[자율매매] 보유 종목 ({len(positions)}개)</b>",
        "",
    ]

    for pos in positions:
        name = pos["name"]
        ticker = pos["ticker"]
        entry = pos["entry_price"]
        stop = pos["stop_loss"]
        t1 = pos["target1"]
        t2 = pos["target2"]
        regime = pos.get("entry_regime", "")
        weight = pos.get("weight_pct", 0)
        entry_date = pos.get("entry_date", "")

        regime_labels = {
            "uptrend": "상승", "downtrend": "하락", "sideways": "횡보",
        }
        regime_kr = regime_labels.get(regime, regime)

        lines.append(f"<b>{name}</b> ({ticker})")
        lines.append(f"  진입: {entry:,}원 ({entry_date})")
        lines.append(f"  비중: {weight:.1f}% | 레짐: {regime_kr}")
        if stop > 0:
            lines.append(f"  손절: {stop:,}원")
        if t1 > 0:
            t1_hit = "✅" if pos.get("target1_hit") else ""
            lines.append(f"  목표1: {t1:,}원 {t1_hit}")
        if t2 > 0:
            t2_hit = "✅" if pos.get("target2_hit") else ""
            lines.append(f"  목표2: {t2:,}원 {t2_hit}")
        lines.append("")

    send_message("\n".join(lines), chat_id=chat_id)
