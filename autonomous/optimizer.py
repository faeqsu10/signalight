"""성과 기반 전략 파라미터 자동 튜닝.

최근 거래 성과를 분석하여 스캔 가중치, 합류 임계값을
보수적으로 조정한다.

가드레일:
- 최소 샘플: 20건 이상 거래 후 활성화
- 조정 범위: 기본값 대비 +-30%
- 합류 임계값: +-0.5 범위
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from autonomous.state import DB_PATH, _get_conn, PipelineState

logger = logging.getLogger("signalight.auto")

# 기본값 (universe.py 하드코딩 값)
DEFAULT_SCAN_WEIGHTS = {
    "golden_cross": 3.0,
    "rsi_oversold": 2.0,
    "volume_surge": 1.0,
}

# 허용 범위 (기본값 +-30%)
SCAN_WEIGHT_BOUNDS = {
    "golden_cross": (2.1, 3.9),
    "rsi_oversold": (1.4, 2.6),
    "volume_surge": (0.7, 1.3),
}

# 기본값 (trading/rules.py / config.py의 임계값)
DEFAULT_BUY_THRESHOLDS = {
    "uptrend": 2.5,
    "sideways": 3.5,
    "downtrend": 4.5,
}

# 임계값 조정 상한
THRESHOLD_ADJUST_MAX = 0.5

# 최소 샘플 수
MIN_TRADES = 20


class StrategyOptimizer:
    """성과 기반 전략 파라미터 자동 튜닝.

    최근 거래 성과를 분석하여 스캔 가중치, 합류 임계값을
    보수적으로 조정한다.

    가드레일:
    - 최소 샘플: 20건 이상 거래 후 활성화
    - 조정 범위: 기본값 대비 +-30%
    - 합류 임계값: +-0.5 범위
    """

    def __init__(self, state: PipelineState = None) -> None:
        self._state = state
        self._ensure_table()

    # ── 퍼블릭 API ──

    def get_optimized_params(self) -> Dict:
        """최적화된 파라미터를 반환한다.

        Returns:
            {
                "scan_weights": {golden_cross, rsi_oversold, volume_surge},
                "buy_thresholds": {uptrend, sideways, downtrend},
                "active": bool,
            }
        """
        defaults = {
            "scan_weights": dict(DEFAULT_SCAN_WEIGHTS),
            "buy_thresholds": dict(DEFAULT_BUY_THRESHOLDS),
            "active": False,
        }

        perf = self.get_scan_performance()
        total_trades = sum(v["total"] for v in perf.values())

        if total_trades < MIN_TRADES:
            logger.debug(
                "최적화 비활성 — 거래 수 부족 (%d / %d)", total_trades, MIN_TRADES
            )
            return defaults

        # 스캔 가중치 조정
        optimized_weights = self._calc_optimized_weights(perf)

        # 전체 승률로 임계값 조정
        total_wins = sum(v["wins"] for v in perf.values())
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        optimized_thresholds = self._calc_optimized_thresholds(overall_win_rate)

        logger.info(
            "파라미터 최적화 적용 — 승률 %.1f%% (샘플 %d건)", overall_win_rate, total_trades
        )

        return {
            "scan_weights": optimized_weights,
            "buy_thresholds": optimized_thresholds,
            "active": True,
        }

    def update_trade_result(
        self,
        ticker: str,
        scan_signals: List[str],
        pnl_pct: float,
    ) -> None:
        """스캔 시그널별 거래 결과를 기록한다.

        각 scan_signal에 대해 개별 행을 삽입한다.

        Args:
            ticker: 종목코드
            scan_signals: 이 거래에 기여한 스캔 시그널 목록
                          예: ["golden_cross", "rsi_oversold"]
            pnl_pct: 손익률 (%)
        """
        if not scan_signals:
            logger.debug("scan_signals 없음, 기록 스킵 (%s)", ticker)
            return

        is_win = 1 if pnl_pct > 0 else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = _get_conn()
        try:
            for signal in scan_signals:
                conn.execute(
                    """INSERT INTO optimizer_scan_results
                       (ticker, scan_signal, pnl_pct, is_win, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (ticker, signal, pnl_pct, is_win, now),
                )
            conn.commit()
            logger.debug(
                "거래 결과 기록 — %s | 시그널: %s | PnL: %.2f%%",
                ticker, scan_signals, pnl_pct,
            )
        finally:
            conn.close()

    def get_scan_performance(self) -> Dict:
        """스캔 시그널별 성과 통계를 반환한다.

        Returns:
            {
                signal_name: {
                    total: int,
                    wins: int,
                    win_rate: float,
                    avg_pnl: float,
                }
            }
        """
        conn = _get_conn()
        try:
            rows = conn.execute(
                """SELECT
                       scan_signal,
                       COUNT(*) as total,
                       SUM(is_win) as wins,
                       AVG(pnl_pct) as avg_pnl
                   FROM optimizer_scan_results
                   GROUP BY scan_signal"""
            ).fetchall()
        finally:
            conn.close()

        result = {}  # type: Dict[str, Dict]

        # 알려진 시그널 타입에 대해 기본값 보장
        for signal in DEFAULT_SCAN_WEIGHTS:
            result[signal] = {"total": 0, "wins": 0, "win_rate": 0.0, "avg_pnl": 0.0}

        for row in rows:
            name = row["scan_signal"]
            total = row["total"] or 0
            wins = int(row["wins"] or 0)
            win_rate = round((wins / total * 100) if total > 0 else 0.0, 1)
            result[name] = {
                "total": total,
                "wins": wins,
                "win_rate": win_rate,
                "avg_pnl": round(row["avg_pnl"] or 0.0, 2),
            }

        return result

    # ── 내부 헬퍼 ──

    def _ensure_table(self) -> None:
        """optimizer_scan_results 테이블이 없으면 생성한다."""
        conn = _get_conn()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS optimizer_scan_results (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ticker TEXT NOT NULL,
                       scan_signal TEXT NOT NULL,
                       pnl_pct REAL NOT NULL,
                       is_win INTEGER NOT NULL DEFAULT 0,
                       created_at TEXT NOT NULL
                   )"""
            )
            conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_opt_scan_signal
                   ON optimizer_scan_results(scan_signal)"""
            )
            conn.commit()
        finally:
            conn.close()

    def _calc_optimized_weights(self, perf: Dict) -> Dict[str, float]:
        """승률에 비례해 스캔 가중치를 조정하고 범위를 클램핑한다.

        승률이 높은 시그널에 더 높은 가중치를 부여한다.
        데이터가 없는 시그널은 기본값을 유지한다.

        조정 로직:
        1. 각 시그널의 승률을 기반으로 새로운 가중치를 비례 산정
        2. 합계를 기본 가중치 합계(6.0)에 맞춰 정규화
        3. 각 시그널별 허용 범위로 클램핑
        """
        default_sum = sum(DEFAULT_SCAN_WEIGHTS.values())  # 6.0

        # 승률 기반 원시 가중치 계산 (데이터 없으면 기본값 사용)
        raw = {}
        for signal, default_w in DEFAULT_SCAN_WEIGHTS.items():
            info = perf.get(signal, {})
            total = info.get("total", 0)
            if total == 0:
                raw[signal] = default_w
            else:
                win_rate = info.get("win_rate", 50.0)
                # 승률을 0~100 → 0.5~1.5 스케일 (50% 승률 = 기본값 유지)
                scale = 0.5 + (win_rate / 100.0)
                raw[signal] = default_w * scale

        # 합계를 기본값 합계에 맞춰 정규화
        raw_sum = sum(raw.values())
        if raw_sum > 0:
            normalized = {k: v * (default_sum / raw_sum) for k, v in raw.items()}
        else:
            normalized = dict(DEFAULT_SCAN_WEIGHTS)

        # 허용 범위로 클램핑
        result = {}
        for signal, value in normalized.items():
            lo, hi = SCAN_WEIGHT_BOUNDS[signal]
            clamped = max(lo, min(hi, value))
            result[signal] = round(clamped, 2)

        logger.debug("스캔 가중치 조정: %s", result)
        return result

    def _calc_optimized_thresholds(self, overall_win_rate: float) -> Dict[str, float]:
        """전체 승률에 따라 합류 임계값을 보수적으로 조정한다.

        - 승률 > 60%: 임계값 소폭 하향 (진입 쉽게, 최대 -0.5)
        - 승률 < 40%: 임계값 소폭 상향 (진입 어렵게, 최대 +0.5)
        - 40~60%: 기본값 유지
        """
        if overall_win_rate > 60.0:
            # 승률이 높을수록 더 크게 조정 (60~100% → 0~-0.5)
            ratio = (overall_win_rate - 60.0) / 40.0  # 0.0~1.0
            adjustment = -round(min(ratio * THRESHOLD_ADJUST_MAX, THRESHOLD_ADJUST_MAX), 2)
            logger.info("임계값 하향 조정 %.2f (승률 %.1f%%)", adjustment, overall_win_rate)
        elif overall_win_rate < 40.0:
            # 승률이 낮을수록 더 크게 조정 (40~0% → 0~+0.5)
            ratio = (40.0 - overall_win_rate) / 40.0  # 0.0~1.0
            adjustment = round(min(ratio * THRESHOLD_ADJUST_MAX, THRESHOLD_ADJUST_MAX), 2)
            logger.info("임계값 상향 조정 +%.2f (승률 %.1f%%)", adjustment, overall_win_rate)
        else:
            adjustment = 0.0

        result = {}
        for regime, default_t in DEFAULT_BUY_THRESHOLDS.items():
            result[regime] = round(default_t + adjustment, 2)

        logger.debug("합류 임계값 조정: %s", result)
        return result
