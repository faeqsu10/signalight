from __future__ import annotations

"""미국 주식 자율 트레이딩 스케줄 러너.

main.py와 완전 독립된 별도 프로세스로 동작한다.
schedule 기반으로 일일 매매 사이클, 장중 모니터링, 주간 평가를 등록한다.

스케줄 (서버 KST 기준, EDT 환산):
    - 23:35 KST (월~금) = 09:35 ET — 장 시작 유니버스 스캔
    - 23:40~05:40 KST (화~토) 5분 간격 = 09:40~15:40 ET — 장중 실시간 모니터링
    - 05:50 KST (화~토) = 15:50 ET — 장 마감 일일 마무리
    - 토요일 06:30 KST = 금요일 16:30 ET — 주간 성과 평가

사용법:
    python3 autonomous/us/runner.py                        # 기본 실행 (dry_run=False, paper, swing)
    python3 autonomous/us/runner.py --live                 # 실제 주문 (dry_run=False)
    python3 autonomous/us/runner.py --live --mode swing    # 단타 봇
    python3 autonomous/us/runner.py --live --mode meanrev  # 평균회귀 봇
    python3 autonomous/us/runner.py --once                 # 1회 실행 후 종료
    python3 autonomous/us/runner.py --help                 # 도움말
"""

import sys
import os
import time
import signal
import logging
import argparse
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import schedule
from infra.logging_config import setup_logging, log_event
from infra.ops_event_store import OpsEventStore
from autonomous.us.config import US_AUTO_CONFIG, US_MEANREV_CONFIG
from autonomous.us.pipeline import USAutonomousPipeline
from bot.telegram import send_message

logger = None  # setup_logging()으로 초기화
DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Signalight US 자율 트레이딩 파이프라인",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="실제 주문 모드 (기본: Alpaca Paper Trading)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="1회 실행 후 종료 (스케줄 등록 안 함)",
    )
    parser.add_argument(
        "--monitor-only", action="store_true",
        help="장중 모니터링만 실행 (매수 없음)",
    )
    parser.add_argument(
        "--mode", choices=["swing", "meanrev"], default="swing",
        help="봇 모드: swing (기본) 또는 meanrev (평균회귀)",
    )
    return parser.parse_args()


def main():
    global logger
    args = parse_args()

    # 모드에 따른 설정 선택
    if args.mode == "meanrev":
        config = US_MEANREV_CONFIG
    else:
        config = US_AUTO_CONFIG

    service_name = "auto-us-meanrev" if args.mode == "meanrev" else "auto-us"
    log_basename = "auto-us-meanrev" if args.mode == "meanrev" else "auto-us"

    logger = setup_logging(service_name=service_name, log_basename=log_basename)
    ops_store = OpsEventStore()

    if args.live:
        config.dry_run = False
        logger.warning("⚠️ US 실제 주문 모드로 시작합니다!")
    else:
        config.dry_run = True
        logger.info("🇺🇸 US 시뮬레이션(Paper Trading) 모드로 시작합니다.")

    ops_store.record_event(
        level="INFO",
        service=service_name,
        event="runner_started",
        message="US runner started",
        context={"mode": args.mode, "live": args.live, "once": args.once},
    )

    pipeline = USAutonomousPipeline(config=config)

    # 시그널 핸들러 (Ctrl+C / SIGTERM — 현재 작업 완료 후 종료)
    _shutdown_requested = False

    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        logger.info("종료 시그널 수신 — 현재 작업 완료 후 종료")
        _shutdown_requested = True
        chat_id = config.auto_trade_chat_id
        if chat_id:
            send_message(
                f"⛔ <b>{config.bot_label} 종료 중...</b>",
                chat_id=chat_id, bot_token=config.bot_token or None,
            )

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    chat_id = config.auto_trade_chat_id
    logger.info("=== Signalight US 자율 트레이딩 시작 (%s) ===", config.bot_label)
    logger.info("모드: %s", "실전" if not config.dry_run else "Paper Trading")
    logger.info("알림 채팅: %s", chat_id if chat_id else "미설정")
    logger.info(
        "포지션 크기: %.1f%% / 최대 %d종목",
        config.target_weight_pct,
        config.max_positions,
    )
    logger.info(
        "서킷 브레이커: 일일 -%.1f%% / 주간 -%.1f%% / %d연패 / MDD -%.1f%%",
        config.daily_loss_limit_pct,
        config.weekly_loss_limit_pct,
        config.max_consecutive_losses,
        config.max_drawdown_pct,
    )

    if chat_id:
        startup_msg = (
            f"✅ <b>{config.bot_label} 파이프라인 시작</b>\n"
            f"모드: {'실전' if not config.dry_run else 'Paper Trading'}\n"
            f"포지션: {config.target_weight_pct:.0f}% × 최대 {config.max_positions}종목"
        )
        send_message(startup_msg, chat_id=chat_id, bot_token=config.bot_token or None)

    if args.once:
        logger.info("1회 실행 모드")
        if args.monitor_only:
            pipeline.run_intraday_monitor()
        else:
            pipeline.run_morning_scan()
            pipeline.run_intraday_monitor()
            pipeline.run_daily_cycle()
        return

    _register_schedules(pipeline, args.monitor_only, config)

    logger.info("US 스케줄 등록 완료. 실행 중... (Ctrl+C로 종료)")

    try:
        while not _shutdown_requested:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.error("스케줄 실행 중 예외 — 루프 유지: %s", e, exc_info=True)
                ops_store.record_event(
                    level="ERROR",
                    service=service_name,
                    event="schedule_loop_error",
                    message=str(e),
                    error_type=type(e).__name__,
                )
            time.sleep(30)
    except Exception as e:
        logger.critical("파이프라인 크래시: %s", e, exc_info=True)
        log_event(logger, logging.CRITICAL, "runner_crash", "US runner crashed", service=service_name, error_type=type(e).__name__)
        ops_store.record_event(
            level="CRITICAL",
            service=service_name,
            event="runner_crash",
            message=str(e),
            error_type=type(e).__name__,
        )
        chat_id = config.auto_trade_chat_id
        if chat_id:
            send_message(
                f"🚨 <b>{config.bot_label} 크래시!</b>\n{str(e)[:200]}",
                chat_id=chat_id, bot_token=config.bot_token or None,
            )
        raise

    logger.info("US 파이프라인 정상 종료")
    ops_store.record_event(
        level="INFO",
        service=service_name,
        event="runner_stopped",
        message="US runner stopped",
    )


def _current_kst_slot() -> tuple[str, str]:
    now = datetime.now()
    return DAY_NAMES[now.weekday()], now.strftime("%H:%M")


def _current_us_time() -> datetime:
    """tzdata 없이도 현재 ET 시각을 얻는다."""
    original_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "America/New_York"
        if hasattr(time, "tzset"):
            time.tzset()
        return datetime.now()
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        if hasattr(time, "tzset"):
            time.tzset()


def _kst_slots_for_et_time(et_day: str, hour: int, minute: int) -> list[tuple[str, str]]:
    """ET 시각을 KST 스케줄 슬롯(EST/EDT 둘 다)으로 변환한다."""
    et_day_index = DAY_NAMES.index(et_day)
    slots = set()
    for kst_offset_hours in (13, 14):  # EDT +13h, EST +14h
        total_minutes = hour * 60 + minute + kst_offset_hours * 60
        day_shift, local_minutes = divmod(total_minutes, 24 * 60)
        local_day = DAY_NAMES[(et_day_index + day_shift) % 7]
        local_hour, local_minute = divmod(local_minutes, 60)
        slots.add((local_day, f"{local_hour:02d}:{local_minute:02d}"))
    return sorted(slots)


def _schedule_tagged(day: str, time_str: str, callback, tag: str):
    return getattr(schedule.every(), day).at(time_str).do(callback).tag(tag)


def _schedule_tagged_once(registered_slots: set, day: str, time_str: str, callback, tag: str):
    slot = (tag, day, time_str)
    if slot in registered_slots:
        return None
    registered_slots.add(slot)
    return _schedule_tagged(day, time_str, callback, tag)


def _run_if_kst_matches_et_time(et_days: tuple[str, ...], target_hour: int, target_minute: int, callback):
    now_et = _current_us_time()
    current_day = DAY_NAMES[now_et.weekday()]
    if current_day not in et_days:
        return None
    if now_et.hour != target_hour or now_et.minute != target_minute:
        return None
    return callback()


def _run_if_kst_matches_et_window(
    et_days: tuple[str, ...],
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    interval: int,
    callback,
):
    now_et = _current_us_time()
    current_day = DAY_NAMES[now_et.weekday()]
    if current_day not in et_days:
        return None

    now_minutes = now_et.hour * 60 + now_et.minute
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    if now_minutes < start_minutes or now_minutes > end_minutes:
        return None
    if now_et.minute % interval != 0:
        return None
    return callback()


def _run_if_kst_matches_weekly(et_day: str, target_hour: int, target_minute: int, callback):
    return _run_if_kst_matches_et_time((et_day,), target_hour, target_minute, callback)


def _register_schedules(pipeline: USAutonomousPipeline, monitor_only: bool, config=None):
    """KST 기준 스케줄을 등록한다.

    ET 기준 거래 시각을 EST/EDT 두 경우의 KST 슬롯으로 모두 등록하고,
    실제 실행 시점에는 현재 US/Eastern 시각으로 한 번 더 검증한다.
    """
    if config is None:
        config = US_AUTO_CONFIG
    interval = config.monitor_interval_min
    registered_slots = set()

    if not monitor_only:
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
            for local_day, local_time in _kst_slots_for_et_time(
                day, config.market_open_hour, config.market_open_minute
            ):
                _schedule_tagged_once(
                    registered_slots,
                    local_day,
                    local_time,
                    lambda cb=pipeline.run_morning_scan, h=config.market_open_hour, m=config.market_open_minute: _run_if_kst_matches_et_time(
                        ("monday", "tuesday", "wednesday", "thursday", "friday"),
                        h,
                        m,
                        cb,
                    ),
                    "us-morning-scan",
                )

        for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
            for local_day, local_time in _kst_slots_for_et_time(
                day, config.market_close_hour, config.market_close_minute
            ):
                _schedule_tagged_once(
                    registered_slots,
                    local_day,
                    local_time,
                    lambda cb=pipeline.run_daily_cycle, h=config.market_close_hour, m=config.market_close_minute: _run_if_kst_matches_et_time(
                        ("monday", "tuesday", "wednesday", "thursday", "friday"),
                        h,
                        m,
                        cb,
                    ),
                    "us-daily-cycle",
                )

        logger.info(
            "스케줄: ET 09:35 / 15:50 기준 KST 슬롯 등록 완료 (EST/EDT 자동 대응)"
        )

    for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        for hour in range(config.market_open_hour, config.market_close_hour + 1):
            for minute in range(0, 60, interval):
                if hour == config.market_open_hour and minute < 40:
                    continue
                if hour == config.market_close_hour and minute > 40:
                    continue
                for local_day, local_time in _kst_slots_for_et_time(day, hour, minute):
                    _schedule_tagged_once(
                        registered_slots,
                        local_day,
                        local_time,
                        lambda cb=pipeline.run_intraday_monitor: _run_if_kst_matches_et_window(
                            ("monday", "tuesday", "wednesday", "thursday", "friday"),
                            config.market_open_hour,
                            40,
                            config.market_close_hour,
                            40,
                            interval,
                            cb,
                        ),
                        "us-intraday-monitor",
                    )

    logger.info(
        "스케줄: ET 09:40~15:40 기준 KST 슬롯 등록 완료 (매수+매도, %d분 간격)",
        interval,
    )

    for local_day, local_time in _kst_slots_for_et_time("friday", 16, 30):
        _schedule_tagged_once(
            registered_slots,
            local_day,
            local_time,
            lambda cb=pipeline.run_weekly_evaluation: _run_if_kst_matches_weekly("friday", 16, 30, cb),
            "us-weekly-evaluation",
        )
    logger.info("스케줄: ET 금요일 16:30 기준 KST 슬롯 등록 완료 (EST/EDT 자동 대응)")


if __name__ == "__main__":
    main()
