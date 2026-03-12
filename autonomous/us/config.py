"""미국 주식 자율 트레이딩 전용 설정."""
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv
from config import US_SECTOR_MAP

load_dotenv()


@dataclass
class USAutonomousConfig:
    """미국 주식 자율 트레이딩 파이프라인 설정."""

    # ── 텔레그램 ──
    auto_trade_chat_id: str = field(
        default_factory=lambda: os.getenv("AUTO_TRADE_CHAT_ID", "")
    )

    # ── 포지션 사이징 ──
    target_weight_pct: float = 10.0       # 종목당 목표 비중 (%)
    max_single_position_pct: float = 15.0  # 종목당 최대 비중 (%)
    max_positions: int = 5                # 최대 동시 보유 종목 수
    max_exposure_pct: float = 80.0        # 최대 총 투자 비중
    max_sector_positions: int = 2         # 같은 섹터 최대 보유 수

    # ── 서킷 브레이커 ──
    daily_loss_limit_pct: float = 3.0     # 일일 손실 한도 (%)
    weekly_loss_limit_pct: float = 5.0    # 주간 손실 한도 (%)
    max_consecutive_losses: int = 5
    max_drawdown_pct: float = 15.0
    consecutive_loss_pause_days: int = 2

    # ── 유니버스 ──
    universe_max_candidates: int = 20
    universe_scan_limit: int = 50
    data_period_days: int = 120

    # ── 지표 설정 ──
    indicator_short_ma: int = 10
    indicator_long_ma: int = 50
    indicator_rsi_period: int = 14
    indicator_rsi_oversold: float = 35.0
    indicator_rsi_overbought: float = 70.0

    # ── 스캔 설정 ──
    scan_rsi_oversold_threshold: float = 40.0
    scan_volume_surge_ratio: float = 1.5
    scan_near_golden_cross_proximity: float = 0.98

    # ── 진입 임계값 ──
    initial_entry_threshold_uptrend: float = 1.5
    initial_entry_threshold_sideways: float = 2.2
    initial_entry_threshold_downtrend: float = 3.0
    initial_min_volume_ratio: float = 0.5

    # ── 매매 설정 ──
    split_buy_phases: int = 3
    split_buy_confirm_days: int = 2
    split_buy_phase3_bonus: float = 1.0
    stop_loss_atr_uptrend: float = 2.5
    stop_loss_atr_sideways: float = 2.0
    stop_loss_atr_downtrend: float = 1.5
    max_loss_pct: float = 8.0
    target1_atr_mult: float = 2.0
    target2_atr_mult: float = 3.5
    trailing_stop_atr_mult: float = 1.5
    max_holding_days: int = 20

    # ── VIX ──
    vix_extreme_fear: float = 30.0
    vix_fear: float = 25.0
    vix_extreme_greed: float = 12.0
    vix_position_mult_calm: float = 1.0
    vix_position_mult_normal: float = 0.8
    vix_position_mult_fear: float = 0.6
    vix_position_mult_extreme: float = 0.5

    # ── 적응형 완화 ──
    universe_min_candidates: int = 3
    universe_max_relaxation_rounds: int = 2
    universe_rsi_relaxation_step: float = 5.0
    universe_volume_relaxation_step: float = 0.3

    # ── 실행 타이밍 (ET 기준) ──
    daily_scan_time: str = "15:50"        # ET 기준 일일 스캔 (장 마감 10분 전)
    monitor_interval_min: int = 5
    market_open_hour: int = 9
    market_open_minute: int = 35          # 09:35 ET부터 주문 허용
    market_close_hour: int = 15
    market_close_minute: int = 50         # 15:50 ET까지 주문 허용
    market_timezone: str = "US/Eastern"   # ET 시간대

    # ── 주문 설정 ──
    dry_run: bool = False                 # False = Alpaca Paper Trading
    max_order_amount: float = 10_000.0    # 1회 최대 주문 금액 (USD)
    order_type: str = "market"

    # ── 킬스위치 ──
    kill_switch_path: str = "/tmp/signalight_us_kill"

    # ── 평가 ──
    evaluation_day: str = "friday"
    evaluation_time: str = "16:30"        # ET

    # ── 가상 자산 ──
    virtual_asset: float = 100_000.0      # Alpaca Paper Trading 기본 자금 (USD)

    # ── 섹터 매핑 ──
    sector_map: dict = field(default_factory=lambda: dict(US_SECTOR_MAP))


US_AUTO_CONFIG = USAutonomousConfig()
