"""자율 트레이딩 파이프라인 실행기.

main.py와 완전 독립된 별도 프로세스로 동작한다.
schedule 기반으로 일일 매매 사이클, 장중 모니터링, 주간 평가를 등록한다.

사용법:
    python3 autonomous/runner.py              # 기본 실행 (dry_run=True)
    python3 autonomous/runner.py --live       # 실제 주문 (dry_run=False)
    python3 autonomous/runner.py --once       # 1회 실행 후 종료
    python3 autonomous/runner.py --help       # 도움말
"""

import sys
import os
import time
import signal
import logging
import argparse
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schedule
from infra.logging_config import setup_logging
from autonomous.config import AUTO_CONFIG
from autonomous.pipeline import AutonomousPipeline

logger = None  # setup_logging()으로 초기화


def parse_args():
    parser = argparse.ArgumentParser(
        description="Signalight 자율 트레이딩 파이프라인",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="실제 주문 모드 (기본: 시뮬레이션)",
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

    # 모드 설정
    if args.live:
        AUTO_CONFIG.dry_run = False
        logger.warning("⚠️ 실제 주문 모드로 시작합니다!")
    else:
        AUTO_CONFIG.dry_run = True
        logger.info("시뮬레이션 모드로 시작합니다.")

    # 파이프라인 생성
    pipeline = AutonomousPipeline()

    # 시그널 핸들러 (Ctrl+C 정리 종료)
    def _signal_handler(signum, frame):
        logger.info("종료 시그널 수신 — 파이프라인 종료")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 상태 출력
    chat_id = AUTO_CONFIG.auto_trade_chat_id
    logger.info("=== Signalight 자율 트레이딩 시작 ===")
    logger.info("모드: %s", "실전" if not AUTO_CONFIG.dry_run else "시뮬레이션")
    logger.info("환경: %s", "모의투자" if AUTO_CONFIG.use_mock else "실전투자")
    logger.info("알림 채팅: %s", chat_id if chat_id else "미설정")
    logger.info("포지션 크기: %.1f%% / 최대 %d종목",
                AUTO_CONFIG.target_weight_pct, AUTO_CONFIG.max_positions)
    logger.info("서킷 브레이커: 일일 -%.1f%% / 주간 -%.1f%% / %d연패 / MDD -%.1f%%",
                AUTO_CONFIG.daily_loss_limit_pct,
                AUTO_CONFIG.weekly_loss_limit_pct,
                AUTO_CONFIG.max_consecutive_losses,
                AUTO_CONFIG.max_drawdown_pct)

    # --once: 1회 실행
    if args.once:
        logger.info("1회 실행 모드")
        if args.monitor_only:
            pipeline.run_intraday_monitor()
        else:
            pipeline.run_daily_cycle()
        return

    # 스케줄 등록
    _register_schedules(pipeline, args.monitor_only)

    logger.info("스케줄 등록 완료. 실행 중... (Ctrl+C로 종료)")

    # 메인 루프
    while True:
        schedule.run_pending()
        time.sleep(30)


def _register_schedules(pipeline: AutonomousPipeline, monitor_only: bool):
    """스케줄을 등록한다."""
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday")

    if not monitor_only:
        # 평일 16:00 — 일일 매매 사이클
        for day in weekdays:
            getattr(schedule.every(), day).at(
                AUTO_CONFIG.daily_scan_time
            ).do(pipeline.run_daily_cycle)
        logger.info("스케줄: 평일 %s — 일일 매매 사이클", AUTO_CONFIG.daily_scan_time)

    # 평일 장중 — 보유종목 모니터링 (5분 간격, 09:05~15:20)
    for day in weekdays:
        for hour in range(9, 16):
            for minute in range(0, 60, AUTO_CONFIG.monitor_interval_min):
                # 09:00~09:04 제외
                if hour == 9 and minute < 5:
                    continue
                # 15:21 이후 제외
                if hour == 15 and minute > 20:
                    continue
                if hour > 15:
                    continue

                t = f"{hour:02d}:{minute:02d}"
                getattr(schedule.every(), day).at(t).do(
                    pipeline.run_intraday_monitor
                )
    logger.info("스케줄: 평일 09:05~15:20 — 보유종목 모니터링 (%d분 간격)",
                AUTO_CONFIG.monitor_interval_min)

    # 주간 성과 평가 (금요일 17:00)
    getattr(schedule.every(), AUTO_CONFIG.evaluation_day).at(
        AUTO_CONFIG.evaluation_time
    ).do(pipeline.run_weekly_evaluation)
    logger.info("스케줄: %s %s — 주간 성과 평가",
                AUTO_CONFIG.evaluation_day, AUTO_CONFIG.evaluation_time)


if __name__ == "__main__":
    main()
