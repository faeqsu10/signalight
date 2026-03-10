"""자율 트레이딩 전용 설정.

기존 config.py의 매매 룰 설정을 상속하면서,
자율 파이프라인 전용 파라미터를 추가한다.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AutonomousConfig:
    """자율 트레이딩 파이프라인 설정."""

    # ── 텔레그램 ──
    auto_trade_chat_id: str = field(
        default_factory=lambda: os.getenv("AUTO_TRADE_CHAT_ID", "")
    )

    # ── 포지션 사이징 (보수적) ──
    target_weight_pct: float = 5.0        # 종목당 목표 비중 (%)
    max_single_position_pct: float = 10.0  # 종목당 최대 비중 (%)
    max_positions: int = 10               # 최대 동시 보유 종목 수
    max_exposure_pct: float = 80.0        # 최대 총 투자 비중 (현금 20% 유지)
    max_sector_positions: int = 3         # 같은 섹터 최대 보유 수

    # ── 서킷 브레이커 ──
    daily_loss_limit_pct: float = 2.0     # 일일 손실 한도 (%)
    weekly_loss_limit_pct: float = 4.0    # 주간 손실 한도 (%)
    max_consecutive_losses: int = 5       # 연속 패배 한도
    max_drawdown_pct: float = 15.0        # 최대 낙폭 킬스위치 (%)
    consecutive_loss_pause_days: int = 2  # 연속 패배 시 정지 영업일 수

    # ── 유니버스 선정 ──
    universe_market: str = "KOSPI"        # 스캔 대상 시장
    universe_max_candidates: int = 30     # 스캔 후보 최대 수
    min_trading_value: int = 5_000_000_000  # 최소 일평균 거래대금 (50억)

    # ── 실행 타이밍 ──
    daily_scan_time: str = "16:00"        # 일일 스캔 시각
    monitor_interval_min: int = 5         # 장중 모니터링 간격 (분)
    market_open_hour: int = 9
    market_open_minute: int = 5           # 09:05부터 주문 허용
    market_close_hour: int = 15
    market_close_minute: int = 20         # 15:20까지 주문 허용

    # ── 주문 설정 ──
    dry_run: bool = True                  # True = 시뮬레이션 (실제 주문 없음)
    use_mock: bool = True                 # True = 키움 모의투자
    max_order_amount: int = 5_000_000     # 1회 최대 주문 금액 (원)
    order_type: str = "market"            # "market" 또는 "limit"

    # ── 킬스위치 ──
    kill_switch_path: str = "/tmp/signalight_kill"

    # ── 평가 ──
    evaluation_day: str = "friday"        # 주간 평가 요일
    evaluation_time: str = "17:00"        # 주간 평가 시각


# 모듈 레벨 싱글턴
AUTO_CONFIG = AutonomousConfig()
