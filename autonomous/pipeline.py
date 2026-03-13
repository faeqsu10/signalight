"""자율 트레이딩 파이프라인 — 메인 오케스트레이터.

스캔 → 분석 → 결정 → 실행 → 추적 → 평가 파이프라인을 관리한다.
"""

import logging
import os
from datetime import date
from typing import List, Dict

from trading.rules import TradeRule
from trading.position_tracker import PositionTracker
from autonomous.config import AUTO_CONFIG
from autonomous.state import PipelineState
from autonomous.universe import UniverseSelector
from autonomous.analyzer import StockAnalyzer
from autonomous.decision import DecisionEngine
from autonomous.execution import SafeExecutor
from autonomous.evaluator import PerformanceEvaluator
from autonomous.optimizer import StrategyOptimizer
from config import DRY_RUN_VIRTUAL_ASSET

logger = logging.getLogger("signalight.auto")


class AutonomousPipeline:
    """자율 트레이딩 파이프라인."""

    def __init__(self):
        self.state = PipelineState()
        self.tracker = PositionTracker()
        self.trade_rule = TradeRule()
        self.optimizer = StrategyOptimizer(state=self.state)

        self.universe = UniverseSelector()
        self.analyzer = StockAnalyzer()
        self.decision = DecisionEngine(
            trade_rule=self.trade_rule,
            position_tracker=self.tracker,
            state=self.state,
        )
        self.executor = SafeExecutor(
            state=self.state,
            position_tracker=self.tracker,
        )
        self.evaluator = PerformanceEvaluator(
            state=self.state,
            position_tracker=self.tracker,
        )
        self._optimizer_status = None
        self._daily_candidates = []   # 장 시작 스캔 후보 캐시
        self._daily_scan_date = None  # 스캔 날짜 (중복 방지)
        self._base_thresholds = {
            "uptrend": AUTO_CONFIG.initial_entry_threshold_uptrend,
            "sideways": AUTO_CONFIG.initial_entry_threshold_sideways,
            "downtrend": AUTO_CONFIG.initial_entry_threshold_downtrend,
        }
        self._base_min_volume_ratio = AUTO_CONFIG.initial_min_volume_ratio
        self._base_rule_overrides = {
            "split_buy_phases": AUTO_CONFIG.split_buy_phases,
            "split_buy_confirm_days": AUTO_CONFIG.split_buy_confirm_days,
            "split_buy_phase3_bonus": AUTO_CONFIG.split_buy_phase3_bonus,
            "stop_loss_atr": {
                "uptrend": AUTO_CONFIG.stop_loss_atr_uptrend,
                "sideways": AUTO_CONFIG.stop_loss_atr_sideways,
                "downtrend": AUTO_CONFIG.stop_loss_atr_downtrend,
            },
            "max_loss_pct": AUTO_CONFIG.max_loss_pct,
            "target1_atr_mult": AUTO_CONFIG.target1_atr_mult,
            "target2_atr_mult": AUTO_CONFIG.target2_atr_mult,
            "trailing_stop_atr_mult": AUTO_CONFIG.trailing_stop_atr_mult,
            "max_holding_days": AUTO_CONFIG.max_holding_days,
            "max_positions": AUTO_CONFIG.max_positions,
            "max_sector_positions": AUTO_CONFIG.max_sector_positions,
            "target_weight_pct": AUTO_CONFIG.target_weight_pct,
            "max_single_position_pct": AUTO_CONFIG.max_single_position_pct,
            "vix_position_mult": {
                "calm": AUTO_CONFIG.vix_position_mult_calm,
                "normal": AUTO_CONFIG.vix_position_mult_normal,
                "fear": AUTO_CONFIG.vix_position_mult_fear,
                "extreme": AUTO_CONFIG.vix_position_mult_extreme,
            },
            "sector_map": AUTO_CONFIG.sector_map,
        }

    def run_daily_cycle(self) -> Dict:
        """장 마감 후 일일 마무리.

        에퀴티 스냅샷, PnL 기록, 일일 요약 전송, 웹 데이터 export.
        매수/매도는 장중 모니터링(run_intraday_monitor)에서 실시간 처리됨.

        Returns:
            일일 결과 요약
        """
        logger.info("=== 일일 마무리 시작 (%s) ===", date.today())

        result = {
            "date": date.today().isoformat(),
            "errors": [],
        }

        # ── 에퀴티 스냅샷 ──
        try:
            self._save_equity_snapshot()
        except Exception as e:
            logger.warning("에퀴티 스냅샷 실패: %s", e)
            result["errors"].append(f"equity: {e}")

        # ── 일일 PnL 기록 ──
        try:
            self._record_daily_pnl()
        except Exception as e:
            logger.warning("일일 PnL 기록 실패: %s", e)

        # ── 일일 요약 전송 ──
        try:
            self.evaluator.daily_summary(optimizer_status=self._optimizer_status)
        except Exception as e:
            logger.warning("일일 요약 전송 실패: %s", e)

        # ── 웹 대시보드 데이터 export + 자동 배포 ──
        try:
            import subprocess
            project_root = os.path.dirname(os.path.dirname(__file__))
            subprocess.run(
                ["python3", "scripts/export_auto_data.py"],
                cwd=project_root,
                timeout=30,
            )
            # autonomous.json을 커밋+푸시하여 Vercel 자동 배포
            data_file = "web/public/data/autonomous.json"
            subprocess.run(["git", "add", data_file], cwd=project_root, timeout=10)
            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--quiet", data_file],
                cwd=project_root, timeout=10,
            )
            if diff_result.returncode != 0:  # 변경사항이 있을 때만 커밋
                subprocess.run(
                    ["git", "commit", "-m", "auto: update autonomous trading data"],
                    cwd=project_root, timeout=15,
                )
                subprocess.Popen(["git", "push"], cwd=project_root)
                logger.info("웹 데이터 export + push 완료")
        except Exception as e:
            logger.warning("웹 데이터 export 실패: %s", e)

        # 내일 스캔을 위해 캐시 초기화
        self._daily_candidates = []
        self._daily_scan_date = None

        logger.info("=== 일일 마무리 완료 ===")
        return result

    def run_morning_scan(self) -> int:
        """장 시작 시 유니버스 스캔 + 후보 캐싱.

        매일 1회 실행. 후보 종목을 분석하고 캐시에 저장한다.
        장중 모니터링에서 이 캐시를 사용하여 매수를 시도한다.

        Returns:
            스캔된 후보 종목 수
        """
        today = date.today()
        if self._daily_scan_date == today:
            logger.info("오늘 스캔 이미 완료 — 스킵")
            return len(self._daily_candidates)

        logger.info("=== 장 시작 유니버스 스캔 (%s) ===", today)

        # VIX/매크로 캐시 초기화
        self.analyzer.clear_cache()
        self.executor.reset_daily()

        # 최적화 파라미터 적용
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
        except Exception as e:
            logger.warning("옵티마이저 파라미터 적용 실패: %s", e)

        # 유니버스 스캔
        held = set(pos["ticker"] for pos in self.tracker.get_all_open())
        candidates = self.universe.select_universe(held_tickers=held)

        if not candidates:
            logger.info("매수 후보 없음")
            self._daily_candidates = []
            self._daily_scan_date = today
            return 0

        logger.info("매수 후보 스캔: %d종목", len(candidates))

        # 후보 분석
        analyzed = self.analyzer.analyze_candidates(candidates)
        self._daily_candidates = analyzed or []
        self._daily_scan_date = today

        logger.info("분석 완료: %d종목 캐시됨", len(self._daily_candidates))

        # 스캔 요약 알림
        try:
            self.evaluator.send_cycle_summary(
                flag="🇰🇷",
                scan_count=len(candidates),
                analyze_count=len(self._daily_candidates),
                buy_count=0,
                sell_count=0,
                top_candidates=self._daily_candidates,
                currency="KRW",
            )
        except Exception as e:
            logger.warning("스캔 요약 전송 실패: %s", e)

        return len(self._daily_candidates)

    def run_intraday_monitor(self) -> Dict:
        """장중 실시간 모니터링 — 매수 + 매도.

        1. 캐시된 후보 종목 중 매수 조건 충족 시 매수
        2. 보유 종목 손절/목표가 도달 시 매도

        Returns:
            {"buys": int, "sells": int}
        """
        result = {"buys": 0, "sells": 0}

        # ── 보유 종목 매도 체크 ──
        open_positions = self.tracker.get_all_open()
        if open_positions:
            holdings_info = [
                {"ticker": pos["ticker"], "name": pos["name"]}
                for pos in open_positions
            ]
            analyzed = self.analyzer.analyze_holdings(holdings_info)
            sell_decisions = self.decision.make_sell_decisions(analyzed)

            for decision in sell_decisions:
                try:
                    order = self.executor.execute_sell(
                        decision["stock_data"],
                        decision["recommendation"],
                        decision["position"],
                    )
                    if order and order.status in ("filled", "simulated"):
                        result["sells"] += 1
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
                        decision["stock_data"]["ticker"], e,
                    )

        # ── 캐시된 후보 매수 체크 ──
        if self._daily_candidates:
            # 이미 보유 중인 종목 제외
            held = set(pos["ticker"] for pos in self.tracker.get_all_open())
            remaining = [
                c for c in self._daily_candidates
                if c.get("ticker") not in held
            ]

            if remaining:
                buy_decisions = self.decision.make_buy_decisions(remaining)
                for decision in buy_decisions:
                    try:
                        order = self.executor.execute_buy(
                            decision["stock_data"],
                            decision["recommendation"],
                        )
                        if order and order.status in ("filled", "simulated"):
                            result["buys"] += 1
                            scan_sigs = decision.get("scan_signals", [])
                            reason_parts = [f"score={decision['confluence_score']:.1f}"]
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
                            # 매수 완료된 종목은 캐시에서 제거
                            self._daily_candidates = [
                                c for c in self._daily_candidates
                                if c.get("ticker") != order.ticker
                            ]
                    except Exception as e:
                        logger.error("매수 실행 실패: %s", e)

        if result["buys"] > 0 or result["sells"] > 0:
            logger.info("장중 모니터링: 매수 %d건, 매도 %d건",
                        result["buys"], result["sells"])

        return result

    def run_weekly_evaluation(self) -> Dict:
        """주간 성과 평가를 실행한다."""
        logger.info("=== 주간 성과 평가 시작 ===")

        # 최근 매도 거래의 결과를 optimizer에 기록
        try:
            self._update_optimizer_with_closed_trades()
        except Exception as e:
            logger.warning("optimizer 거래 결과 갱신 실패: %s", e)

        return self.evaluator.weekly_report()

    # ── 내부 메서드 ──

    def _phase_sell(self) -> int:
        """매도 판단 + 실행."""
        open_positions = self.tracker.get_all_open()
        if not open_positions:
            logger.info("보유 종목 없음 — 매도 판단 스킵")
            return 0

        logger.info("보유 종목 매도 판단: %d종목", len(open_positions))

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

    def _phase_buy(self) -> Dict:
        """유니버스 스캔 + 분석 + 매수 결정 + 실행.

        Returns:
            {"buys": int, "scan_count": int, "analyze_count": int, "top_candidates": list}
        """
        phase_result = {
            "buys": 0,
            "scan_count": 0,
            "analyze_count": 0,
            "top_candidates": [],
        }

        # 보유 종목 ticker 수집 (제외용)
        held = set(pos["ticker"] for pos in self.tracker.get_all_open())

        # 유니버스 스캔
        candidates = self.universe.select_universe(held_tickers=held)
        if not candidates:
            logger.info("매수 후보 없음")
            return phase_result

        phase_result["scan_count"] = len(candidates)
        logger.info("매수 후보 스캔: %d종목", len(candidates))

        # 후보 분석
        analyzed = self.analyzer.analyze_candidates(candidates)
        if not analyzed:
            logger.info("분석 통과 종목 없음")
            return phase_result

        phase_result["analyze_count"] = len(analyzed)
        phase_result["top_candidates"] = analyzed

        # 상위 3개 후보 로깅
        top3 = sorted(
            analyzed, key=lambda x: x.get("confluence_score", 0), reverse=True
        )[:3]
        for item in top3:
            logger.info(
                "상위 후보: %s(%s) score=%.1f signals=%s",
                item.get("name", ""), item.get("ticker", ""),
                item.get("confluence_score", 0),
                item.get("scan_signals", []),
            )

        # 매수 결정
        buy_decisions = self.decision.make_buy_decisions(analyzed)
        if not buy_decisions:
            logger.info("매수 조건 충족 종목 없음")
            return phase_result

        # 매수 결정 로깅
        for dec in buy_decisions:
            sd = dec["stock_data"]
            logger.info(
                "매수 결정: %s(%s) score=%.1f reason=%s",
                sd.get("name", ""), sd.get("ticker", ""),
                dec.get("confluence_score", 0),
                dec["recommendation"].get("action", ""),
            )

        # 매수 실행
        buy_count = 0
        for decision in buy_decisions:
            try:
                order = self.executor.execute_buy(
                    decision["stock_data"],
                    decision["recommendation"],
                )
                if order and order.status in ("filled", "simulated"):
                    buy_count += 1
                    # scan_signals를 reason에 포함 (optimizer 추적용)
                    scan_sigs = decision.get("scan_signals", [])
                    reason_parts = [f"score={decision['confluence_score']:.1f}"]
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

        phase_result["buys"] = buy_count
        return phase_result

    def _save_equity_snapshot(self) -> None:
        """에퀴티 스냅샷을 저장한다."""
        open_positions = self.tracker.get_all_open()

        # 보유 포지션이 있을 때만 API 평가 사용
        if open_positions and self.executor.portfolio:
            evaluation = self.executor.portfolio._get_evaluation()
            if evaluation:
                summary = evaluation["summary"]
                self.state.save_equity_snapshot(
                    total_equity=summary.get("estimated_asset", 0),
                    invested=summary.get("total_purchase", 0),
                    cash=summary.get("deposit", 0),
                    open_positions=len(open_positions),
                )
                return

        # 포지션 없음 또는 평가 실패: 가상 에퀴티 사용
        self.state.save_equity_snapshot(
            total_equity=DRY_RUN_VIRTUAL_ASSET,
            invested=0,
            cash=DRY_RUN_VIRTUAL_ASSET,
            open_positions=len(open_positions),
        )

    def _record_daily_pnl(self) -> None:
        """일일 PnL을 기록한다."""
        today = date.today().isoformat()
        trades = self.state.get_recent_trades(days=1)

        # 오늘 매도 거래의 PnL 합산
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
        """최근 청산된 포지션의 결과를 optimizer에 기록한다.

        position_tracker의 closed 포지션 중 optimizer에 아직
        기록되지 않은 거래를 찾아서 update_trade_result()를 호출한다.
        """
        closed = self.tracker.get_closed_positions()
        recent_trades = self.state.get_recent_trades(days=7)

        # 최근 7일 매도 거래 (pnl_pct 존재)
        sell_trades = [
            t for t in recent_trades
            if t["side"] == "sell" and t.get("pnl_pct") is not None
        ]

        for trade in sell_trades:
            ticker = trade["ticker"]
            pnl_pct = trade["pnl_pct"]

            # 해당 종목의 매수 거래에서 scan_signals 찾기
            buy_trades = [
                t for t in recent_trades
                if t["ticker"] == ticker and t["side"] == "buy"
            ]

            # reason 필드에서 scan_signals 추출 시도
            scan_signals = []
            for bt in buy_trades:
                reason = bt.get("reason", "") or ""
                for sig in ["golden_cross", "near_golden_cross", "rsi_oversold", "volume_surge"]:
                    if sig in reason and sig not in scan_signals:
                        scan_signals.append(sig)

            if scan_signals:
                self.optimizer.update_trade_result(
                    ticker=ticker,
                    scan_signals=scan_signals,
                    pnl_pct=pnl_pct,
                )
