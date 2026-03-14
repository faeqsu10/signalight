"""자율 트레이딩 파이프라인 실행기.

main.py와 완전 독립된 별도 프로세스로 동작한다.
schedule 기반으로 일일 매매 사이클, 장중 모니터링, 주간 평가를 등록한다.

사용법:
    python3 autonomous/runner.py                       # 기본 실행 (dry_run=True, swing)
    python3 autonomous/runner.py --live                # 실제 주문 (dry_run=False)
    python3 autonomous/runner.py --live --mode swing   # 단타 봇
    python3 autonomous/runner.py --live --mode position # 장기 봇
    python3 autonomous/runner.py --once                # 1회 실행 후 종료
    python3 autonomous/runner.py --help                # 도움말
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
    parser.add_argument(
        "--mode", choices=["swing", "position"], default="swing",
        help="봇 모드: swing (단타) 또는 position (장기)",
    )
    return parser.parse_args()


def main():
    global logger
    logger = setup_logging()

    args = parse_args()

    # 모드에 따른 설정 선택
    if args.mode == "position":
        from autonomous.config import POSITION_CONFIG
        config = POSITION_CONFIG
    else:
        from autonomous.config import SWING_CONFIG
        config = SWING_CONFIG

    # 모드 설정
    if args.live:
        config.dry_run = False
        logger.warning("⚠️ 실제 주문 모드로 시작합니다!")
    else:
        config.dry_run = True
        logger.info("시뮬레이션 모드로 시작합니다.")

    # 파이프라인 생성
    pipeline = AutonomousPipeline(config=config)

    # 시그널 핸들러 (Ctrl+C / SIGTERM — 현재 작업 완료 후 종료)
    _shutdown_requested = False

    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        logger.info("종료 시그널 수신 — 현재 작업 완료 후 종료")
        _shutdown_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 상태 출력
    chat_id = config.auto_trade_chat_id
    logger.info("=== Signalight 자율 트레이딩 시작 (%s) ===", config.bot_label)
    logger.info("모드: %s", "실전" if not config.dry_run else "시뮬레이션")
    logger.info("환경: %s", "모의투자" if config.use_mock else "실전투자")
    logger.info("알림 채팅: %s", chat_id if chat_id else "미설정")
    logger.info("포지션 크기: %.1f%% / 최대 %d종목",
                config.target_weight_pct, config.max_positions)
    logger.info("서킷 브레이커: 일일 -%.1f%% / 주간 -%.1f%% / %d연패 / MDD -%.1f%%",
                config.daily_loss_limit_pct,
                config.weekly_loss_limit_pct,
                config.max_consecutive_losses,
                config.max_drawdown_pct)

    # --once: 1회 실행 (스캔 + 모니터링 1회)
    if args.once:
        logger.info("1회 실행 모드")
        if args.monitor_only:
            pipeline.run_intraday_monitor()
        else:
            pipeline.run_morning_scan()
            pipeline.run_intraday_monitor()
            pipeline.run_daily_cycle()
        return

    # 스케줄 등록
    _register_schedules(pipeline, args.monitor_only, config)

    logger.info("스케줄 등록 완료. 실행 중... (Ctrl+C로 종료)")

    # 메인 루프
    while not _shutdown_requested:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error("스케줄 실행 중 예외 — 루프 유지: %s", e, exc_info=True)
        time.sleep(30)

    logger.info("파이프라인 정상 종료")


def _register_schedules(pipeline: AutonomousPipeline, monitor_only: bool, config):
    """스케줄을 등록한다.

    흐름:
        09:05 — 장 시작 유니버스 스캔 (후보 캐싱)
        09:10~15:20 — 장중 실시간 모니터링 (매수 + 매도, 5분 간격)
        15:25 — 장 마감 일일 마무리 (에퀴티, PnL, 요약)
    """
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday")

    if not monitor_only:
        # 평일 09:05 — 장 시작 유니버스 스캔
        for day in weekdays:
            getattr(schedule.every(), day).at("09:05").do(
                pipeline.run_morning_scan
            )
        logger.info("스케줄: 평일 09:05 — 장 시작 유니버스 스캔")

        # 평일 15:25 — 장 마감 일일 마무리
        for day in weekdays:
            getattr(schedule.every(), day).at("15:25").do(
                pipeline.run_daily_cycle
            )
        logger.info("스케줄: 평일 15:25 — 장 마감 일일 마무리")

    # 평일 장중 — 실시간 모니터링 (매수 + 매도, 5분 간격, 09:10~15:20)
    for day in weekdays:
        for hour in range(9, 16):
            for minute in range(0, 60, config.monitor_interval_min):
                # 09:00~09:09 제외 (09:05에 스캔이 돌기 때문)
                if hour == 9 and minute < 10:
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
    logger.info("스케줄: 평일 09:10~15:20 — 장중 실시간 모니터링 (매수+매도, %d분 간격)",
                config.monitor_interval_min)

    # 주간 성과 평가 (금요일 17:00)
    getattr(schedule.every(), config.evaluation_day).at(
        config.evaluation_time
    ).do(pipeline.run_weekly_evaluation)
    logger.info("스케줄: %s %s — 주간 성과 평가",
                config.evaluation_day, config.evaluation_time)


if __name__ == "__main__":
    main()
