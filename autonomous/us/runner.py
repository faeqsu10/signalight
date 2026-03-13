"""미국 주식 자율 트레이딩 스케줄 러너.

main.py와 완전 독립된 별도 프로세스로 동작한다.
schedule 기반으로 일일 매매 사이클, 장중 모니터링, 주간 평가를 등록한다.

스케줄 (서버 KST 기준, EDT 환산):
    - 23:35 KST (월~금) = 09:35 ET — 장 시작 유니버스 스캔
    - 23:40~05:40 KST (화~토) 5분 간격 = 09:40~15:40 ET — 장중 실시간 모니터링
    - 05:50 KST (화~토) = 15:50 ET — 장 마감 일일 마무리
    - 토요일 06:30 KST = 금요일 16:30 ET — 주간 성과 평가

사용법:
    python3 autonomous/us/runner.py              # 기본 실행 (dry_run=False, paper)
    python3 autonomous/us/runner.py --live       # 실제 주문 (dry_run=False)
    python3 autonomous/us/runner.py --once       # 1회 실행 후 종료
    python3 autonomous/us/runner.py --help       # 도움말
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
from infra.logging_config import setup_logging
from autonomous.us.config import US_AUTO_CONFIG
from autonomous.us.pipeline import USAutonomousPipeline

logger = None  # setup_logging()으로 초기화


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
    return parser.parse_args()


def main():
    global logger
    logger = setup_logging()

    args = parse_args()

    if args.live:
        US_AUTO_CONFIG.dry_run = False
        logger.warning("⚠️ US 실제 주문 모드로 시작합니다!")
    else:
        US_AUTO_CONFIG.dry_run = True
        logger.info("🇺🇸 US 시뮬레이션(Paper Trading) 모드로 시작합니다.")

    pipeline = USAutonomousPipeline()

    # 시그널 핸들러 (Ctrl+C / SIGTERM — 현재 작업 완료 후 종료)
    _shutdown_requested = False

    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        logger.info("종료 시그널 수신 — 현재 작업 완료 후 종료")
        _shutdown_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    chat_id = US_AUTO_CONFIG.auto_trade_chat_id
    logger.info("=== Signalight US 자율 트레이딩 시작 ===")
    logger.info("모드: %s", "실전" if not US_AUTO_CONFIG.dry_run else "Paper Trading")
    logger.info("알림 채팅: %s", chat_id if chat_id else "미설정")
    logger.info(
        "포지션 크기: %.1f%% / 최대 %d종목",
        US_AUTO_CONFIG.target_weight_pct,
        US_AUTO_CONFIG.max_positions,
    )
    logger.info(
        "서킷 브레이커: 일일 -%.1f%% / 주간 -%.1f%% / %d연패 / MDD -%.1f%%",
        US_AUTO_CONFIG.daily_loss_limit_pct,
        US_AUTO_CONFIG.weekly_loss_limit_pct,
        US_AUTO_CONFIG.max_consecutive_losses,
        US_AUTO_CONFIG.max_drawdown_pct,
    )

    if args.once:
        logger.info("1회 실행 모드")
        if args.monitor_only:
            pipeline.run_intraday_monitor()
        else:
            pipeline.run_morning_scan()
            pipeline.run_intraday_monitor()
            pipeline.run_daily_cycle()
        return

    _register_schedules(pipeline, args.monitor_only)

    logger.info("US 스케줄 등록 완료. 실행 중... (Ctrl+C로 종료)")

    while not _shutdown_requested:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error("스케줄 실행 중 예외 — 루프 유지: %s", e, exc_info=True)
        time.sleep(30)

    logger.info("US 파이프라인 정상 종료")


def _register_schedules(pipeline: USAutonomousPipeline, monitor_only: bool):
    """KST 기준 스케줄을 등록한다.

    3단계 흐름 (KST 기준, EDT +13h):
        23:35 KST (월~금) = 09:35 ET — 장 시작 유니버스 스캔
        23:40~05:40 KST (화~토) = 09:40~15:40 ET — 장중 실시간 모니터링 (매수+매도)
        05:50 KST (화~토) = 15:50 ET — 장 마감 일일 마무리

    서머타임(EDT, 3월~11월) 적용 시 1시간 빠름.
    서버를 KST로 운영하므로 KST 기준 시각으로 등록.
    """
    interval = US_AUTO_CONFIG.monitor_interval_min

    if not monitor_only:
        # 평일 23:35 KST (월~금) = 09:35 ET — 장 시작 유니버스 스캔
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
            getattr(schedule.every(), day).at("23:35").do(
                pipeline.run_morning_scan
            )
        logger.info("스케줄: 월~금 23:35 KST (09:35 ET) — US 장 시작 유니버스 스캔")

        # 화~토 05:50 KST = 15:50 ET — 장 마감 일일 마무리
        for day in ("tuesday", "wednesday", "thursday", "friday", "saturday"):
            getattr(schedule.every(), day).at("05:50").do(
                pipeline.run_daily_cycle
            )
        logger.info("스케줄: 화~토 05:50 KST (15:50 ET) — US 장 마감 일일 마무리")

    # 장중 실시간 모니터링 (매수+매도): KST 23:40~05:40, 5분 간격

    # KST 23:40~23:55 구간 (ET 09:40~09:55): 월~금에 등록
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        for minute in range(40, 60, interval):
            t = f"23:{minute:02d}"
            getattr(schedule.every(), day).at(t).do(
                pipeline.run_intraday_monitor
            )

    # KST 00:00~05:40 구간 (ET 10:00~15:40): 화~토에 등록
    for day in ("tuesday", "wednesday", "thursday", "friday", "saturday"):
        for hour in range(0, 6):
            for minute in range(0, 60, interval):
                # 05:45 이후 제외 (05:50에 daily_cycle)
                if hour == 5 and minute >= 45:
                    continue
                t = f"{hour:02d}:{minute:02d}"
                getattr(schedule.every(), day).at(t).do(
                    pipeline.run_intraday_monitor
                )

    logger.info(
        "스케줄: 23:40~05:40 KST — US 장중 실시간 모니터링 (매수+매도, %d분 간격)",
        interval,
    )

    # 주간 성과 평가: 토요일 06:30 KST = 금요일 16:30 ET
    schedule.every().saturday.at("06:30").do(pipeline.run_weekly_evaluation)
    logger.info("스케줄: 토요일 06:30 KST (금요일 16:30 ET) — US 주간 성과 평가")


if __name__ == "__main__":
    main()
