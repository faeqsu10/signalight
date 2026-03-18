"""자율 트레이딩 전용 설정.

기존 config.py의 매매 룰 설정을 상속하면서,
자율 파이프라인 전용 파라미터를 추가한다.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from config import SECTOR_MAP

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
    universe_max_candidates: int = 50     # 스캔 후보 최대 수
    universe_scan_limit: int = 50         # 각 스캔(골든/RSI/거래량) 최대 조회 수
    min_trading_value: int = 3_000_000_000  # 최소 일평균 거래대금 (30억)
    data_period_days: int = 120           # 자율매매 데이터 조회 기간
    indicator_short_ma: int = 10
    indicator_long_ma: int = 50
    indicator_rsi_period: int = 14
    indicator_rsi_oversold: float = 35.0
    indicator_rsi_overbought: float = 70.0
    indicator_stoch_rsi_period: int = 14
    indicator_stoch_rsi_smooth_k: int = 3
    indicator_stoch_rsi_smooth_d: int = 3
    indicator_stoch_rsi_oversold: float = 20.0
    indicator_stoch_rsi_overbought: float = 80.0
    investor_consec_days: int = 3
    vix_extreme_fear: float = 28.0
    vix_fear: float = 25.0
    vix_extreme_greed: float = 12.0
    scan_rsi_oversold_threshold: float = 45.0  # RSI 과매도 스캔 기준 (완화)
    scan_volume_surge_ratio: float = 1.3       # 거래량 급증 스캔 배수 (완화)
    scan_near_golden_cross_proximity: float = 0.98  # 근접 골든크로스 short/long MA 비율 하한
    universe_min_candidates: int = 3           # 최소 후보 수 (미달 시 적응형 완화)
    universe_max_relaxation_rounds: int = 2    # 적응형 완화 최대 라운드
    universe_rsi_relaxation_step: float = 5.0  # 라운드당 RSI 완화 폭
    universe_volume_relaxation_step: float = 0.3  # 라운드당 거래량 비율 완화 폭
    initial_entry_threshold_uptrend: float = 0.8   # 초기 진입 임계값(상승장, 적극적)
    initial_entry_threshold_sideways: float = 1.0  # 초기 진입 임계값(횡보장, 적극적)
    initial_entry_threshold_downtrend: float = 1.5 # 초기 진입 임계값(하락장, 적극적)
    initial_min_volume_ratio: float = 0.3          # 초기 거래량 필터(적극적)
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
    vix_position_mult_calm: float = 1.0
    vix_position_mult_normal: float = 0.8
    vix_position_mult_fear: float = 0.6
    vix_position_mult_extreme: float = 0.5
    sector_map: dict = field(default_factory=lambda: dict(SECTOR_MAP))

    # ── 봇 모드 ──
    bot_mode: str = "swing"
    bot_label: str = "🇰🇷 단타"
    enabled_indicators: list = field(default_factory=lambda: None)
    bot_token: str = field(default_factory=lambda: "")
    db_name: str = "signalight_swing.db"
    fixed_target_pct: float = 0.0  # 0이면 ATR 기반, >0이면 고정 퍼센트 목표
    skip_trend_gate: bool = False  # True이면 추세 게이트 스킵 (평균회귀용)
    quick_profit_take_pct: float = 0.0  # 소폭 이익 후 빠른 청산 허용
    quick_profit_take_requires_non_buy: bool = True  # 비매수 상태일 때만 빠른 청산

    # ── 피드백 루프(optimizer) ──
    optimizer_default_weight_golden_cross: float = 3.0
    optimizer_default_weight_rsi_oversold: float = 2.0
    optimizer_default_weight_volume_surge: float = 1.0

    optimizer_weight_min_golden_cross: float = 2.1
    optimizer_weight_max_golden_cross: float = 3.9
    optimizer_weight_min_rsi_oversold: float = 1.4
    optimizer_weight_max_rsi_oversold: float = 2.6
    optimizer_weight_min_volume_surge: float = 0.7
    optimizer_weight_max_volume_surge: float = 1.3

    optimizer_threshold_adjust_max: float = 0.5
    optimizer_min_trades: int = 50
    optimizer_lookback_days: int = 30
    optimizer_wf_folds: int = 3
    optimizer_wf_min_validation: int = 5
    optimizer_wf_required_pass_ratio: float = 0.67
    optimizer_min_metric_improvement: float = 0.15

    # ── 실행 타이밍 ──
    daily_scan_time: str = "16:00"        # 일일 스캔 시각
    monitor_interval_min: int = 5         # 장중 모니터링 간격 (분)
    market_open_hour: int = 9
    market_open_minute: int = 5           # 09:05부터 주문 허용
    market_close_hour: int = 15
    market_close_minute: int = 20         # 15:20까지 주문 허용

    # ── 주문 설정 ──
    dry_run: bool = False                 # False = 모의투자 API로 실제 주문
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

# ── 단타 (Swing) 봇 설정 ──
SWING_CONFIG = AutonomousConfig(
    bot_mode="swing",
    bot_label="🇰🇷 단타",
    enabled_indicators=["MA", "RSI", "STOCH_RSI"],
    db_name="signalight_swing.db",
    # 단타 전용: 공격적 초기 설정 (데이터 수집 우선)
    initial_entry_threshold_uptrend=0.3,
    initial_entry_threshold_sideways=0.5,
    initial_entry_threshold_downtrend=0.8,
    max_holding_days=10,
    split_buy_phases=2,
    split_buy_confirm_days=1,
    target1_atr_mult=1.5,
    target2_atr_mult=2.5,
    trailing_stop_atr_mult=1.0,
    stop_loss_atr_uptrend=2.0,
    stop_loss_atr_sideways=1.5,
    stop_loss_atr_downtrend=1.2,
    target_weight_pct=3.0,
    max_positions=15,
    max_sector_positions=4,
)

# ── 장기 (Position) 봇 설정 ──
POSITION_CONFIG = AutonomousConfig(
    bot_mode="position",
    bot_label="🇰🇷 장기",
    enabled_indicators=["MA", "MACD", "INVESTOR", "VIX"],
    bot_token=os.getenv("LONG_BOT_TOKEN", ""),
    auto_trade_chat_id=os.getenv("LONG_TRADE_CHAT_ID", os.getenv("AUTO_TRADE_CHAT_ID", "")),
    db_name="signalight_position.db",
    # 장기 전용: 높은 임계값, 긴 보유
    initial_entry_threshold_uptrend=1.0,
    initial_entry_threshold_sideways=1.2,
    initial_entry_threshold_downtrend=1.5,
    max_holding_days=60,
    split_buy_phases=3,
    split_buy_confirm_days=3,
    target1_atr_mult=3.0,
    target2_atr_mult=5.0,
    trailing_stop_atr_mult=2.0,
    stop_loss_atr_uptrend=3.0,
    stop_loss_atr_sideways=2.5,
    stop_loss_atr_downtrend=2.0,
    max_loss_pct=10.0,
    target_weight_pct=7.0,
    max_positions=8,
    max_sector_positions=2,
)

# ── 평균회귀 (Mean Reversion) 봇 설정 ──
MEANREV_CONFIG = AutonomousConfig(
    bot_mode="meanrev",
    bot_label="🔄 평균회귀",
    enabled_indicators=["RSI"],  # RSI만 사용
    bot_token=os.getenv("MEANREV_BOT_TOKEN", ""),
    auto_trade_chat_id=os.getenv("MEANREV_CHAT_ID", os.getenv("AUTO_TRADE_CHAT_ID", "")),
    db_name="signalight_meanrev.db",
    # 평균회귀 전용: 더 넓게 스캔하고 더 빨리 정리
    kill_switch_path="/tmp/signalight_meanrev_kill",
    scan_rsi_oversold_threshold=50.0,
    scan_volume_surge_ratio=1.0,
    scan_near_golden_cross_proximity=0.96,
    initial_entry_threshold_uptrend=0.1,    # 거의 무조건 진입
    initial_entry_threshold_sideways=0.1,
    initial_entry_threshold_downtrend=0.2,
    initial_min_volume_ratio=0.2,           # 거래량 필터 완화
    max_holding_days=5,
    split_buy_phases=1,            # 분할매수 없음 — 한 번에 매수
    split_buy_confirm_days=0,
    target1_atr_mult=1.5,
    target2_atr_mult=3.0,
    trailing_stop_atr_mult=1.0,
    stop_loss_atr_uptrend=2.0,
    stop_loss_atr_sideways=2.0,
    stop_loss_atr_downtrend=2.0,
    max_loss_pct=5.0,
    target_weight_pct=4.0,
    max_positions=10,
    max_sector_positions=4,        # 섹터 제한 완화
    indicator_rsi_oversold=35.0,   # RSI 35 이하 매수 (공격적 확대)
    fixed_target_pct=2.0,
    skip_trend_gate=True,          # 추세 게이트 스킵
    quick_profit_take_pct=1.0,
    quick_profit_take_requires_non_buy=False,
)
