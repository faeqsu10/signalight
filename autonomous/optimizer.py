"""성과 기반 전략 파라미터 자동 튜닝.

최근 N일 성과를 기준으로 후보 파라미터를 생성하고,
Walk-forward 비교를 통과한 경우에만 자동 적용한다.
변경/미변경 판단은 별도 이력 테이블에 저장한다.
"""

import json
import logging
import math
from datetime import datetime
from statistics import mean, pstdev
from typing import Dict, List, Optional

from autonomous.config import AUTO_CONFIG
from autonomous.state import _get_conn, PipelineState

logger = logging.getLogger("signalight.auto")


class StrategyOptimizer:
    """성과 기반 전략 파라미터 자동 튜닝.

    최근 거래 성과를 분석하여 스캔 가중치, 합류 임계값을
    보수적으로 조정한다.

    가드레일:
    - 조정 대상 제한: scan_weights, buy_thresholds만
    - 최근 N일 성과 기준 + Walk-forward 후보 비교
    - 개선폭 임계값 이상일 때만 반영
    - 변경 이력 별도 저장
    """

    def __init__(self, state: PipelineState = None) -> None:
        self._state = state

        # 설정 기반 파라미터
        self.default_scan_weights = {
            "golden_cross": AUTO_CONFIG.optimizer_default_weight_golden_cross,
            "rsi_oversold": AUTO_CONFIG.optimizer_default_weight_rsi_oversold,
            "volume_surge": AUTO_CONFIG.optimizer_default_weight_volume_surge,
        }
        self.scan_weight_bounds = {
            "golden_cross": (
                AUTO_CONFIG.optimizer_weight_min_golden_cross,
                AUTO_CONFIG.optimizer_weight_max_golden_cross,
            ),
            "rsi_oversold": (
                AUTO_CONFIG.optimizer_weight_min_rsi_oversold,
                AUTO_CONFIG.optimizer_weight_max_rsi_oversold,
            ),
            "volume_surge": (
                AUTO_CONFIG.optimizer_weight_min_volume_surge,
                AUTO_CONFIG.optimizer_weight_max_volume_surge,
            ),
        }
        self.default_buy_thresholds = {
            "uptrend": AUTO_CONFIG.initial_entry_threshold_uptrend,
            "sideways": AUTO_CONFIG.initial_entry_threshold_sideways,
            "downtrend": AUTO_CONFIG.initial_entry_threshold_downtrend,
        }
        self.threshold_adjust_max = AUTO_CONFIG.optimizer_threshold_adjust_max
        self.min_trades = AUTO_CONFIG.optimizer_min_trades
        self.lookback_days = AUTO_CONFIG.optimizer_lookback_days
        self.wf_folds = AUTO_CONFIG.optimizer_wf_folds
        self.wf_min_validation = AUTO_CONFIG.optimizer_wf_min_validation
        self.wf_required_pass_ratio = AUTO_CONFIG.optimizer_wf_required_pass_ratio
        self.min_metric_improvement = AUTO_CONFIG.optimizer_min_metric_improvement

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
            "scan_weights": dict(self.default_scan_weights),
            "buy_thresholds": dict(self.default_buy_thresholds),
            "default_scan_weights": dict(self.default_scan_weights),
            "default_buy_thresholds": dict(self.default_buy_thresholds),
            "active": False,
            "total_trades": 0,
            "overall_win_rate": 0.0,
            "min_trades": self.min_trades,
            "lookback_days": self.lookback_days,
            "wf_folds": self.wf_folds,
            "wf_min_validation": self.wf_min_validation,
            "improvement_threshold": self.min_metric_improvement,
            "baseline_metric": 0.0,
            "candidate_metric": 0.0,
            "avg_improvement": 0.0,
            "wf_passes": 0,
            "wf_valid_folds": 0,
            "wf_required_passes": 0,
            "adjustment_reason": "",
            "latest_change": None,
        }

        recent_rows = self._get_recent_scan_rows(days=self.lookback_days)
        total_trades = len(recent_rows)
        overall_win_rate = self._calc_win_rate(recent_rows)
        defaults["total_trades"] = total_trades
        defaults["overall_win_rate"] = round(overall_win_rate, 1)
        defaults["baseline_metric"] = round(
            self._calc_metric(recent_rows, self.default_scan_weights), 3
        )

        if total_trades < self.min_trades:
            reason = (
                f"최근 {self.lookback_days}일 샘플 부족 ({total_trades}/{self.min_trades})"
            )
            defaults["adjustment_reason"] = reason
            self._record_change_history(
                applied=False,
                reason=reason,
                sample_count=total_trades,
                baseline_metric=defaults["baseline_metric"],
                candidate_metric=defaults["baseline_metric"],
                avg_improvement=0.0,
                wf_passes=0,
                wf_valid_folds=0,
                wf_required_passes=0,
                before_scan=self.default_scan_weights,
                after_scan=self.default_scan_weights,
                before_thresholds=self.default_buy_thresholds,
                after_thresholds=self.default_buy_thresholds,
                before_win_rate=overall_win_rate,
                after_win_rate=overall_win_rate,
            )
            defaults["latest_change"] = self.get_latest_change()
            logger.debug(
                "최적화 비활성 — %s", reason
            )
            return defaults

        # 최근 N일 데이터로 후보 생성 (대상 제한)
        perf_recent = self._build_performance_from_rows(recent_rows)
        candidate_weights = self._calc_optimized_weights(perf_recent)
        candidate_thresholds = self._calc_optimized_thresholds(overall_win_rate)
        candidate_metric = self._calc_metric(recent_rows, candidate_weights)
        defaults["candidate_metric"] = round(candidate_metric, 3)

        # 후보 비교는 Walk-forward만 사용
        wf = self._walk_forward_compare(recent_rows)
        defaults["avg_improvement"] = round(wf["avg_improvement"], 3)
        defaults["wf_passes"] = wf["passes"]
        defaults["wf_valid_folds"] = wf["valid_folds"]
        defaults["wf_required_passes"] = wf["required_passes"]

        is_wf_pass = (
            wf["valid_folds"] > 0
            and wf["passes"] >= wf["required_passes"]
            and wf["avg_improvement"] >= self.min_metric_improvement
        )

        if not is_wf_pass:
            reason = (
                f"최근 {self.lookback_days}일 WF 미통과: "
                f"{wf['passes']}/{wf['valid_folds']} folds, "
                f"개선 {wf['avg_improvement']:+.2f} < +{self.min_metric_improvement:.2f}"
            )
            defaults["adjustment_reason"] = reason
            self._record_change_history(
                applied=False,
                reason=reason,
                sample_count=total_trades,
                baseline_metric=wf["avg_baseline_metric"],
                candidate_metric=wf["avg_candidate_metric"],
                avg_improvement=wf["avg_improvement"],
                wf_passes=wf["passes"],
                wf_valid_folds=wf["valid_folds"],
                wf_required_passes=wf["required_passes"],
                before_scan=self.default_scan_weights,
                after_scan=self.default_scan_weights,
                before_thresholds=self.default_buy_thresholds,
                after_thresholds=self.default_buy_thresholds,
                before_win_rate=overall_win_rate,
                after_win_rate=overall_win_rate,
            )
            defaults["latest_change"] = self.get_latest_change()
            logger.info("파라미터 유지 — %s", reason)
            return defaults

        reason = (
            f"최근 {self.lookback_days}일 WF Sharpe {wf['avg_improvement']:+.2f} 개선 "
            f"({wf['passes']}/{wf['valid_folds']} folds 통과)"
        )
        self._record_change_history(
            applied=True,
            reason=reason,
            sample_count=total_trades,
            baseline_metric=wf["avg_baseline_metric"],
            candidate_metric=wf["avg_candidate_metric"],
            avg_improvement=wf["avg_improvement"],
            wf_passes=wf["passes"],
            wf_valid_folds=wf["valid_folds"],
            wf_required_passes=wf["required_passes"],
            before_scan=self.default_scan_weights,
            after_scan=candidate_weights,
            before_thresholds=self.default_buy_thresholds,
            after_thresholds=candidate_thresholds,
            before_win_rate=overall_win_rate,
            after_win_rate=overall_win_rate,
        )

        logger.info("파라미터 최적화 적용 — %s", reason)

        return {
            "scan_weights": candidate_weights,
            "buy_thresholds": candidate_thresholds,
            "default_scan_weights": dict(self.default_scan_weights),
            "default_buy_thresholds": dict(self.default_buy_thresholds),
            "active": True,
            "total_trades": total_trades,
            "overall_win_rate": round(overall_win_rate, 1),
            "min_trades": self.min_trades,
            "lookback_days": self.lookback_days,
            "wf_folds": self.wf_folds,
            "wf_min_validation": self.wf_min_validation,
            "improvement_threshold": self.min_metric_improvement,
            "baseline_metric": round(wf["avg_baseline_metric"], 3),
            "candidate_metric": round(wf["avg_candidate_metric"], 3),
            "avg_improvement": round(wf["avg_improvement"], 3),
            "wf_passes": wf["passes"],
            "wf_valid_folds": wf["valid_folds"],
            "wf_required_passes": wf["required_passes"],
            "adjustment_reason": reason,
            "latest_change": self.get_latest_change(),
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
        for signal in self.default_scan_weights:
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

    def get_latest_change(self) -> Optional[Dict]:
        """최근 변경(또는 미변경 판단) 이력을 반환한다."""
        conn = _get_conn()
        try:
            row = conn.execute(
                """SELECT evaluated_at, applied, reason, sample_count,
                          baseline_metric, candidate_metric, avg_improvement,
                          wf_passes, wf_valid_folds, wf_required_passes,
                          before_scan_weights, after_scan_weights,
                          before_buy_thresholds, after_buy_thresholds
                   FROM optimizer_change_history
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            for key in (
                "before_scan_weights",
                "after_scan_weights",
                "before_buy_thresholds",
                "after_buy_thresholds",
            ):
                if item.get(key):
                    item[key] = json.loads(item[key])
            return item
        finally:
            conn.close()

    # ── 내부 헬퍼 ──

    def _ensure_table(self) -> None:
        """optimizer 관련 테이블이 없으면 생성한다."""
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
            conn.execute(
                """CREATE TABLE IF NOT EXISTS optimizer_change_history (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       evaluated_at TEXT NOT NULL,
                       applied INTEGER NOT NULL DEFAULT 0,
                       reason TEXT NOT NULL,
                       sample_count INTEGER NOT NULL DEFAULT 0,
                       window_days INTEGER NOT NULL DEFAULT 30,
                       min_trades INTEGER NOT NULL DEFAULT 20,
                       wf_folds INTEGER NOT NULL DEFAULT 3,
                       wf_passes INTEGER NOT NULL DEFAULT 0,
                       wf_valid_folds INTEGER NOT NULL DEFAULT 0,
                       wf_required_passes INTEGER NOT NULL DEFAULT 0,
                       improvement_threshold REAL NOT NULL DEFAULT 0.0,
                       baseline_metric REAL NOT NULL DEFAULT 0.0,
                       candidate_metric REAL NOT NULL DEFAULT 0.0,
                       avg_improvement REAL NOT NULL DEFAULT 0.0,
                       before_win_rate REAL NOT NULL DEFAULT 0.0,
                       after_win_rate REAL NOT NULL DEFAULT 0.0,
                       before_scan_weights TEXT NOT NULL,
                       after_scan_weights TEXT NOT NULL,
                       before_buy_thresholds TEXT NOT NULL,
                       after_buy_thresholds TEXT NOT NULL
                   )"""
            )
            conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_opt_change_eval
                   ON optimizer_change_history(evaluated_at)"""
            )
            conn.commit()
        finally:
            conn.close()

    def _record_change_history(
        self,
        applied: bool,
        reason: str,
        sample_count: int,
        baseline_metric: float,
        candidate_metric: float,
        avg_improvement: float,
        wf_passes: int,
        wf_valid_folds: int,
        wf_required_passes: int,
        before_scan: Dict[str, float],
        after_scan: Dict[str, float],
        before_thresholds: Dict[str, float],
        after_thresholds: Dict[str, float],
        before_win_rate: float,
        after_win_rate: float,
    ) -> None:
        """변경/미변경 판단 이력을 저장한다."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO optimizer_change_history (
                       evaluated_at, applied, reason, sample_count,
                       window_days, min_trades, wf_folds, wf_passes,
                       wf_valid_folds, wf_required_passes, improvement_threshold,
                       baseline_metric, candidate_metric, avg_improvement,
                       before_win_rate, after_win_rate,
                       before_scan_weights, after_scan_weights,
                       before_buy_thresholds, after_buy_thresholds
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now,
                    1 if applied else 0,
                    reason,
                    sample_count,
                    self.lookback_days,
                    self.min_trades,
                    self.wf_folds,
                    wf_passes,
                    wf_valid_folds,
                    wf_required_passes,
                    self.min_metric_improvement,
                    float(baseline_metric),
                    float(candidate_metric),
                    float(avg_improvement),
                    float(before_win_rate),
                    float(after_win_rate),
                    json.dumps(before_scan, ensure_ascii=True, sort_keys=True),
                    json.dumps(after_scan, ensure_ascii=True, sort_keys=True),
                    json.dumps(before_thresholds, ensure_ascii=True, sort_keys=True),
                    json.dumps(after_thresholds, ensure_ascii=True, sort_keys=True),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _get_recent_scan_rows(self, days: int) -> List[Dict]:
        conn = _get_conn()
        try:
            rows = conn.execute(
                """SELECT scan_signal, pnl_pct, is_win, created_at
                   FROM optimizer_scan_results
                   WHERE created_at >= datetime('now', ?)
                   ORDER BY created_at ASC, id ASC""",
                (f"-{days} days",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _build_performance_from_rows(self, rows: List[Dict]) -> Dict[str, Dict]:
        perf = {
            s: {"total": 0, "wins": 0, "win_rate": 0.0, "avg_pnl": 0.0}
            for s in self.default_scan_weights
        }
        pnl_map = {s: [] for s in self.default_scan_weights}

        for row in rows:
            signal = row.get("scan_signal")
            if signal not in perf:
                continue
            pnl = float(row.get("pnl_pct") or 0.0)
            win = int(row.get("is_win") or 0)
            perf[signal]["total"] += 1
            perf[signal]["wins"] += win
            pnl_map[signal].append(pnl)

        for signal, info in perf.items():
            total = info["total"]
            wins = info["wins"]
            info["win_rate"] = round((wins / total * 100.0) if total > 0 else 0.0, 1)
            info["avg_pnl"] = round(mean(pnl_map[signal]), 2) if pnl_map[signal] else 0.0

        return perf

    def _calc_win_rate(self, rows: List[Dict]) -> float:
        if not rows:
            return 0.0
        wins = sum(1 for r in rows if (r.get("is_win") or 0) == 1)
        return wins / len(rows) * 100.0

    def _calc_metric(self, rows: List[Dict], scan_weights: Dict[str, float]) -> float:
        """가중 수익률 기반 간이 Sharpe(metric)를 계산한다."""
        if not rows:
            return 0.0

        weighted_returns = []
        for row in rows:
            signal = row.get("scan_signal")
            if signal not in self.default_scan_weights:
                continue
            pnl = float(row.get("pnl_pct") or 0.0)
            base_w = self.default_scan_weights[signal]
            cur_w = scan_weights.get(signal, base_w)
            adjusted = pnl * (cur_w / base_w if base_w > 0 else 1.0)
            weighted_returns.append(adjusted)

        if not weighted_returns:
            return 0.0

        avg_ret = mean(weighted_returns)
        vol = pstdev(weighted_returns)
        if vol <= 0:
            return avg_ret
        return avg_ret / vol

    def _walk_forward_compare(self, rows: List[Dict]) -> Dict[str, float]:
        """Walk-forward로 baseline vs candidate를 비교한다."""
        n = len(rows)
        if n < max(self.min_trades, self.wf_min_validation * 2):
            return {
                "valid_folds": 0,
                "passes": 0,
                "required_passes": 0,
                "avg_improvement": 0.0,
                "avg_baseline_metric": 0.0,
                "avg_candidate_metric": 0.0,
            }

        # 비겹침 walk-forward: 3개 fold
        # fold 1: train=[0, 33%), val=[33%, 50%)
        # fold 2: train=[0, 50%), val=[50%, 67%)
        # fold 3: train=[0, 67%), val=[67%, 100%)
        folds = [
            (0.33, 0.50),
            (0.50, 0.67),
            (0.67, 1.00),
        ]
        fold_results = []
        for train_end_ratio, val_end_ratio in folds:
            train_end = int(n * train_end_ratio)
            val_end = int(n * val_end_ratio)
            train_rows = rows[:train_end]
            val_rows = rows[train_end:val_end]

            if (
                len(train_rows) < self.min_trades
                or len(val_rows) < self.wf_min_validation
            ):
                continue

            train_perf = self._build_performance_from_rows(train_rows)
            candidate_weights = self._calc_optimized_weights(train_perf)

            baseline_metric = self._calc_metric(val_rows, self.default_scan_weights)
            candidate_metric = self._calc_metric(val_rows, candidate_weights)
            improvement = candidate_metric - baseline_metric

            fold_results.append(
                {
                    "baseline_metric": baseline_metric,
                    "candidate_metric": candidate_metric,
                    "improvement": improvement,
                    "pass": 1 if improvement >= self.min_metric_improvement else 0,
                }
            )

        valid_folds = len(fold_results)
        if valid_folds == 0:
            return {
                "valid_folds": 0,
                "passes": 0,
                "required_passes": 0,
                "avg_improvement": 0.0,
                "avg_baseline_metric": 0.0,
                "avg_candidate_metric": 0.0,
            }

        passes = sum(r["pass"] for r in fold_results)
        required_passes = max(
            1, math.ceil(valid_folds * self.wf_required_pass_ratio)
        )
        avg_improvement = mean(r["improvement"] for r in fold_results)
        avg_baseline = mean(r["baseline_metric"] for r in fold_results)
        avg_candidate = mean(r["candidate_metric"] for r in fold_results)

        return {
            "valid_folds": valid_folds,
            "passes": passes,
            "required_passes": required_passes,
            "avg_improvement": float(avg_improvement),
            "avg_baseline_metric": float(avg_baseline),
            "avg_candidate_metric": float(avg_candidate),
        }

    def _calc_optimized_weights(self, perf: Dict) -> Dict[str, float]:
        """승률에 비례해 스캔 가중치를 조정하고 범위를 클램핑한다.

        승률이 높은 시그널에 더 높은 가중치를 부여한다.
        데이터가 없는 시그널은 기본값을 유지한다.

        조정 로직:
        1. 각 시그널의 승률을 기반으로 새로운 가중치를 비례 산정
        2. 합계를 기본 가중치 합계(6.0)에 맞춰 정규화
        3. 각 시그널별 허용 범위로 클램핑
        """
        default_sum = sum(self.default_scan_weights.values())  # 6.0

        # 승률 기반 원시 가중치 계산 (데이터 없으면 기본값 사용)
        raw = {}
        for signal, default_w in self.default_scan_weights.items():
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
            normalized = dict(self.default_scan_weights)

        # 허용 범위로 클램핑
        result = {}
        for signal, value in normalized.items():
            lo, hi = self.scan_weight_bounds[signal]
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
            adjustment = -round(min(ratio * self.threshold_adjust_max, self.threshold_adjust_max), 2)
            logger.info("임계값 하향 조정 %.2f (승률 %.1f%%)", adjustment, overall_win_rate)
        elif overall_win_rate < 40.0:
            # 승률이 낮을수록 더 크게 조정 (40~0% → 0~+0.5)
            ratio = (40.0 - overall_win_rate) / 40.0  # 0.0~1.0
            adjustment = round(min(ratio * self.threshold_adjust_max, self.threshold_adjust_max), 2)
            logger.info("임계값 상향 조정 +%.2f (승률 %.1f%%)", adjustment, overall_win_rate)
        else:
            adjustment = 0.0

        result = {}
        for regime, default_t in self.default_buy_thresholds.items():
            result[regime] = round(default_t + adjustment, 2)

        logger.debug("합류 임계값 조정: %s", result)
        return result
