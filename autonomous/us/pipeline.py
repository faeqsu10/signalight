"""미국 주식 자율 트레이딩 파이프라인 — 메인 오케스트레이터.

스캔 → 분석 → 결정 → 실행 → 추적 → 평가 파이프라인을 관리한다.
"""

import logging
import os
from datetime import date
from typing import Dict, List

from trading.rules import TradeRule
from trading.position_tracker import PositionTracker
from autonomous.us.config import US_AUTO_CONFIG
from autonomous.state import PipelineState
from autonomous.us.universe import USUniverseSelector
from autonomous.us.analyzer import USStockAnalyzer
from autonomous.decision import DecisionEngine
from autonomous.us.execution import USSafeExecutor
from autonomous.evaluator import PerformanceEvaluator
from autonomous.optimizer import StrategyOptimizer
from config import DRY_RUN_VIRTUAL_ASSET_USD

logger = logging.getLogger("signalight.us")


class USAutonomousPipeline:
    """미국 주식 자율 트레이딩 파이프라인."""

    def __init__(self):
        self.state = PipelineState()
        self.tracker = PositionTracker()
        self.trade_rule = TradeRule()
        self.optimizer = StrategyOptimizer(state=self.state)

        self.universe = USUniverseSelector()
        self.analyzer = USStockAnalyzer()
        self.decision = DecisionEngine(
            trade_rule=self.trade_rule,
            position_tracker=self.tracker,
            state=self.state,
        )
        self.executor = USSafeExecutor(
            state=self.state,
            position_tracker=self.tracker,
        )
        self.evaluator = PerformanceEvaluator(
            state=self.state,
            position_tracker=self.tracker,
        )
        self._optimizer_status = None
        self._base_thresholds = {
            "uptrend": US_AUTO_CONFIG.initial_entry_threshold_uptrend,
            "sideways": US_AUTO_CONFIG.initial_entry_threshold_sideways,
            "downtrend": US_AUTO_CONFIG.initial_entry_threshold_downtrend,
        }
        self._base_min_volume_ratio = US_AUTO_CONFIG.initial_min_volume_ratio
        self._base_rule_overrides = {
            "split_buy_phases": US_AUTO_CONFIG.split_buy_phases,
            "split_buy_confirm_days": US_AUTO_CONFIG.split_buy_confirm_days,
            "split_buy_phase3_bonus": US_AUTO_CONFIG.split_buy_phase3_bonus,
            "stop_loss_atr": {
                "uptrend": US_AUTO_CONFIG.stop_loss_atr_uptrend,
                "sideways": US_AUTO_CONFIG.stop_loss_atr_sideways,
                "downtrend": US_AUTO_CONFIG.stop_loss_atr_downtrend,
            },
            "max_loss_pct": US_AUTO_CONFIG.max_loss_pct,
            "target1_atr_mult": US_AUTO_CONFIG.target1_atr_mult,
            "target2_atr_mult": US_AUTO_CONFIG.target2_atr_mult,
            "trailing_stop_atr_mult": US_AUTO_CONFIG.trailing_stop_atr_mult,
            "max_holding_days": US_AUTO_CONFIG.max_holding_days,
            "max_positions": US_AUTO_CONFIG.max_positions,
            "max_sector_positions": US_AUTO_CONFIG.max_sector_positions,
            "target_weight_pct": US_AUTO_CONFIG.target_weight_pct,
            "max_single_position_pct": US_AUTO_CONFIG.max_single_position_pct,
            "vix_position_mult": {
                "calm": US_AUTO_CONFIG.vix_position_mult_calm,
                "normal": US_AUTO_CONFIG.vix_position_mult_normal,
                "fear": US_AUTO_CONFIG.vix_position_mult_fear,
                "extreme": US_AUTO_CONFIG.vix_position_mult_extreme,
            },
            "sector_map": US_AUTO_CONFIG.sector_map,
        }

    def run_daily_cycle(self) -> Dict:
        """일일 매매 사이클을 실행한다.

        1. 보유 종목 매도 판단
        2. 유니버스 스캔
        3. 후보 분석
        4. 매수 결정
        5. 주문 실행
        6. 에퀴티 스냅샷
        7. 일일 PnL 기록
        8. 일일 요약 전송

        Returns:
            사이클 결과 요약
        """
        logger.info("🇺🇸 === US 일일 매매 사이클 시작 (%s) ===", date.today())

        result = {
            "date": date.today().isoformat(),
            "sells": 0,
            "buys": 0,
            "errors": [],
        }

        # VIX/매크로 캐시 초기화 (매 사이클마다 새로 조회)
        self.analyzer.clear_cache()
        self.executor.reset_daily()

        # ── Phase 0: 최적화 파라미터 적용 ──
        try:
            self.trade_rule.set_entry_threshold_overrides(self._base_thresholds)
            self.trade_rule.set_min_volume_ratio_override(self._base_min_volume_ratio)
            self.trade_rule.set_rule_overrides(self._base_rule_overrides)

            opt_params = self.optimizer.get_optimized_params()
            self._optimizer_status = opt_params
            self.universe.scan_weights = opt_params["scan_weights"]
            if opt_params["active"]:
                self.trade_rule.set_entry_threshold_overrides(
                    opt_params["buy_thresholds"]
                )
                logger.info(
                    "최적화 파라미터 적용 — 가중치: %s, 임계값: %s",
                    opt_params["scan_weights"], opt_params["buy_thresholds"],
                )
        except Exception as e:
            logger.warning("최적화 파라미터 로드 실패: %s", e)
            self._optimizer_status = None
            self.universe.scan_weights = dict(self.universe.scan_weights)
            self.trade_rule.set_entry_threshold_overrides(self._base_thresholds)
            self.trade_rule.set_min_volume_ratio_override(self._base_min_volume_ratio)
            self.trade_rule.set_rule_overrides(self._base_rule_overrides)

        # ── Phase 1: 보유 종목 매도 판단 ──
        try:
            result["sells"] = self._phase_sell()
        except Exception as e:
            logger.error("매도 판단 실패: %s", e)
            result["errors"].append(f"sell: {e}")

        # ── Phase 2: 유니버스 스캔 + 분석 + 매수 ──
        try:
            result["buys"] = self._phase_buy()
        except Exception as e:
            logger.error("매수 판단 실패: %s", e)
            result["errors"].append(f"buy: {e}")

        # ── Phase 3: 에퀴티 스냅샷 ──
        try:
            self._save_equity_snapshot()
        except Exception as e:
            logger.warning("에퀴티 스냅샷 실패: %s", e)

        # ── Phase 4: 일일 PnL 기록 ──
        try:
            self._record_daily_pnl()
        except Exception as e:
            logger.warning("일일 PnL 기록 실패: %s", e)

        # ── Phase 5: 일일 요약 전송 ──
        try:
            self.evaluator.daily_summary(optimizer_status=self._optimizer_status)
        except Exception as e:
            logger.warning("일일 요약 전송 실패: %s", e)

        logger.info(
            "🇺🇸 === US 일일 매매 사이클 완료: 매수 %d건, 매도 %d건 ===",
            result["buys"], result["sells"],
        )
        return result

    def run_intraday_monitor(self) -> int:
        """장중 보유종목 손절 모니터링.

        Returns:
            매도 실행 건수
        """
        open_positions = self.tracker.get_all_open()
        if not open_positions:
            return 0

        holdings_info = [
            {"ticker": pos["ticker"], "name": pos["name"]}
            for pos in open_positions
        ]
        analyzed = self.analyzer.analyze_holdings(holdings_info)
        sell_decisions = self.decision.make_sell_decisions(analyzed)

        sell_count = 0
        for decision in sell_decisions:
            try:
                order = self.executor.execute_sell(
                    decision["stock_data"],
                    decision["recommendation"],
                    decision["position"],
                )
                if order and order.status in ("filled", "simulated"):
                    sell_count += 1
                    self.evaluator.send_trade_notification(
                        side="sell",
                        name=order.name,
                        ticker=order.ticker,
                        quantity=order.quantity,
                        price=order.price,
                        reason=decision["recommendation"].get("action", ""),
                        pnl_pct=decision["recommendation"].get("pnl_pct"),
                    )
            except Exception as e:
                logger.error(
                    "매도 실행 실패: %s(%s) — %s",
                    decision["stock_data"]["name"],
                    decision["stock_data"]["ticker"],
                    e,
                )

        if sell_count > 0:
            logger.info("🇺🇸 장중 모니터링: %d건 매도", sell_count)

        return sell_count

    def run_weekly_evaluation(self) -> Dict:
        """주간 성과 평가를 실행한다."""
        logger.info("🇺🇸 === US 주간 성과 평가 시작 ===")

        try:
            self._update_optimizer_with_closed_trades()
        except Exception as e:
            logger.warning("optimizer 거래 결과 갱신 실패: %s", e)

        return self.evaluator.weekly_report()

    # ── 내부 메서드 ──

    def _phase_sell(self) -> int:
        """보유 종목 매도 판단 + 실행."""
        open_positions = self.tracker.get_all_open()
        if not open_positions:
            logger.info("보유 종목 없음 — 매도 판단 스킵")
            return 0

        logger.info("🇺🇸 보유 종목 매도 판단: %d종목", len(open_positions))

        holdings_info = [
            {"ticker": pos["ticker"], "name": pos["name"]}
            for pos in open_positions
        ]
        analyzed = self.analyzer.analyze_holdings(holdings_info)
        sell_decisions = self.decision.make_sell_decisions(analyzed)

        sell_count = 0
        for decision in sell_decisions:
            try:
                order = self.executor.execute_sell(
                    decision["stock_data"],
                    decision["recommendation"],
                    decision["position"],
                )
                if order and order.status in ("filled", "simulated"):
                    sell_count += 1
                    self.evaluator.send_trade_notification(
                        side="sell",
                        name=order.name,
                        ticker=order.ticker,
                        quantity=order.quantity,
                        price=order.price,
                        reason=decision["recommendation"].get("action", ""),
                        pnl_pct=decision["recommendation"].get("pnl_pct"),
                    )
            except Exception as e:
                logger.error("매도 실행 실패: %s", e)

        return sell_count

    def _phase_buy(self) -> int:
        """유니버스 스캔 + 분석 + 매수 결정 + 실행."""
        held = set(pos["ticker"] for pos in self.tracker.get_all_open())

        candidates = self.universe.select_universe(held_tickers=held)
        if not candidates:
            logger.info("🇺🇸 매수 후보 없음")
            return 0

        logger.info("🇺🇸 매수 후보 스캔: %d종목", len(candidates))

        analyzed = self.analyzer.analyze_candidates(candidates)
        if not analyzed:
            logger.info("🇺🇸 분석 통과 종목 없음")
            return 0

        buy_decisions = self.decision.make_buy_decisions(analyzed)
        if not buy_decisions:
            logger.info("🇺🇸 매수 조건 충족 종목 없음")
            return 0

        buy_count = 0
        for decision in buy_decisions:
            try:
                order = self.executor.execute_buy(
                    decision["stock_data"],
                    decision["recommendation"],
                )
                if order and order.status in ("filled", "simulated"):
                    buy_count += 1
                    scan_sigs = decision.get("scan_signals", [])
                    reason_parts = [
                        f"score={decision['confluence_score']:.1f}"
                    ]
                    if scan_sigs:
                        reason_parts.append("scans=" + ",".join(scan_sigs))
                    self.evaluator.send_trade_notification(
                        side="buy",
                        name=order.name,
                        ticker=order.ticker,
                        quantity=order.quantity,
                        price=order.price,
                        reason=" ".join(reason_parts),
                    )
            except Exception as e:
                logger.error("매수 실행 실패: %s", e)

        return buy_count

    def _save_equity_snapshot(self) -> None:
        """에퀴티 스냅샷을 저장한다."""
        open_positions = self.tracker.get_all_open()

        if open_positions and not self.executor.config.dry_run:
            acct = self.executor.get_account_info()
            if acct:
                total_equity = float(acct.get("equity", DRY_RUN_VIRTUAL_ASSET_USD))
                cash = float(acct.get("cash", 0))
                invested = total_equity - cash
                self.state.save_equity_snapshot(
                    total_equity=int(total_equity * 100),  # cents
                    invested=int(invested * 100),
                    cash=int(cash * 100),
                    open_positions=len(open_positions),
                )
                return

        # 포지션 없음 또는 dry_run: 가상 에퀴티 사용
        self.state.save_equity_snapshot(
            total_equity=int(DRY_RUN_VIRTUAL_ASSET_USD * 100),
            invested=0,
            cash=int(DRY_RUN_VIRTUAL_ASSET_USD * 100),
            open_positions=len(open_positions),
        )

    def _record_daily_pnl(self) -> None:
        """일일 PnL을 기록한다."""
        today = date.today().isoformat()
        trades = self.state.get_recent_trades(days=1)

        today_trades = [t for t in trades if t["trade_date"] == today]
        sells = [t for t in today_trades if t["side"] == "sell"]

        realized_pnl = sum(t.get("pnl_amount", 0) or 0 for t in sells)
        wins = sum(1 for t in sells if (t.get("pnl_amount") or 0) > 0)
        losses = sum(1 for t in sells if (t.get("pnl_amount") or 0) < 0)

        self.state.record_daily_pnl(
            trade_date=today,
            realized_pnl=realized_pnl,
            trades=len(today_trades),
            wins=wins,
            losses=losses,
        )

    def _update_optimizer_with_closed_trades(self) -> None:
        """최근 청산된 포지션의 결과를 optimizer에 기록한다."""
        recent_trades = self.state.get_recent_trades(days=7)

        sell_trades = [
            t for t in recent_trades
            if t["side"] == "sell" and t.get("pnl_pct") is not None
        ]

        for trade in sell_trades:
            ticker = trade["ticker"]
            pnl_pct = trade["pnl_pct"]

            buy_trades = [
                t for t in recent_trades
                if t["ticker"] == ticker and t["side"] == "buy"
            ]

            scan_signals = []
            for bt in buy_trades:
                reason = bt.get("reason", "") or ""
                for sig in ["golden_cross", "rsi_oversold", "volume_surge",
                            "near_golden_cross"]:
                    if sig in reason and sig not in scan_signals:
                        scan_signals.append(sig)

            if scan_signals:
                self.optimizer.update_trade_result(
                    ticker=ticker,
                    scan_signals=scan_signals,
                    pnl_pct=pnl_pct,
                )
