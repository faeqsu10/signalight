"""자율 트레이딩 파이프라인 — 메인 오케스트레이터.

스캔 → 분석 → 결정 → 실행 → 추적 → 평가 파이프라인을 관리한다.
"""

import logging
import os
from datetime import date
from typing import List, Dict
from collections import Counter
from uuid import uuid4

from trading.rules import TradeRule
from trading.position_tracker import PositionTracker
from autonomous.state import PipelineState
from autonomous.universe import UniverseSelector
from autonomous.analyzer import StockAnalyzer
from autonomous.decision import DecisionEngine
from autonomous.execution import SafeExecutor
from autonomous.evaluator import PerformanceEvaluator
from autonomous.optimizer import StrategyOptimizer
from config import DRY_RUN_VIRTUAL_ASSET
from infra.logging_config import log_event
from infra.ops_event_store import OpsEventStore

logger = logging.getLogger("signalight.auto")


class AutonomousPipeline:
    """자율 트레이딩 파이프라인."""

    def __init__(self, config=None):
        from autonomous.config import AUTO_CONFIG
        self.config = config or AUTO_CONFIG

        # DB path for state and tracker
        db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
        db_path = os.path.join(db_dir, self.config.db_name)

        self.state = PipelineState(db_path=db_path)
        self.tracker = PositionTracker(db_path=db_path)
        self.trade_rule = TradeRule()
        self.optimizer = StrategyOptimizer(state=self.state)

        self.universe = UniverseSelector()
        self.analyzer = StockAnalyzer(config=self.config)
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
            config=self.config,
        )
        self.ops_store = OpsEventStore()
        self.service_name = "auto-kr"
        self._optimizer_status = None
        self._daily_candidates = []   # 장 시작 스캔 후보 캐시
        self._daily_scan_date = None  # 스캔 날짜 (중복 방지)
        self._base_thresholds = {
            "uptrend": self.config.initial_entry_threshold_uptrend,
            "sideways": self.config.initial_entry_threshold_sideways,
            "downtrend": self.config.initial_entry_threshold_downtrend,
        }
        self._base_min_volume_ratio = self.config.initial_min_volume_ratio
        self._base_rule_overrides = {
            "split_buy_phases": self.config.split_buy_phases,
            "split_buy_confirm_days": self.config.split_buy_confirm_days,
            "split_buy_phase3_bonus": self.config.split_buy_phase3_bonus,
            "stop_loss_atr": {
                "uptrend": self.config.stop_loss_atr_uptrend,
                "sideways": self.config.stop_loss_atr_sideways,
                "downtrend": self.config.stop_loss_atr_downtrend,
            },
            "max_loss_pct": self.config.max_loss_pct,
            "target1_atr_mult": self.config.target1_atr_mult,
            "target2_atr_mult": self.config.target2_atr_mult,
            "trailing_stop_atr_mult": self.config.trailing_stop_atr_mult,
            "max_holding_days": self.config.max_holding_days,
            "max_positions": self.config.max_positions,
            "max_sector_positions": self.config.max_sector_positions,
            "target_weight_pct": self.config.target_weight_pct,
            "max_single_position_pct": self.config.max_single_position_pct,
            "vix_position_mult": {
                "calm": self.config.vix_position_mult_calm,
                "normal": self.config.vix_position_mult_normal,
                "fear": self.config.vix_position_mult_fear,
                "extreme": self.config.vix_position_mult_extreme,
            },
            "sector_map": self.config.sector_map,
            "fixed_target_pct": self.config.fixed_target_pct,
            "skip_trend_gate": self.config.skip_trend_gate,
        }

    def _new_cycle_id(self, cycle_type: str) -> str:
        service_name = getattr(self, "service_name", "auto-kr")
        return f"{service_name}:{cycle_type}:{date.today().isoformat()}:{uuid4().hex[:8]}"

    def _record_ops_event(self, level: str, event: str, message: str, cycle_id: str = "", **context) -> None:
        store = getattr(self, "ops_store", None) or OpsEventStore()
        service_name = getattr(self, "service_name", "auto-kr")
        store.record_event(
            level=level,
            service=service_name,
            event=event,
            message=message,
            cycle_id=cycle_id or None,
            ticker=context.get("ticker"),
            order_id=context.get("order_id"),
            status=context.get("status"),
            error_type=context.get("error_type"),
            context=context,
        )

    def _start_run(self, cycle_type: str, summary: Dict = None) -> str:
        cycle_id = self._new_cycle_id(cycle_type)
        store = getattr(self, "ops_store", None) or OpsEventStore()
        service_name = getattr(self, "service_name", "auto-kr")
        store.start_run(service_name, cycle_id, summary=summary)
        log_event(
            logger, logging.INFO, f"{cycle_type}_started",
            f"{cycle_type} started",
            cycle_id=cycle_id,
            service=service_name,
        )
        return cycle_id

    def _finish_run(
        self,
        cycle_type: str,
        cycle_id: str,
        status: str,
        summary: Dict = None,
    ) -> None:
        summary = summary or {}
        store = getattr(self, "ops_store", None) or OpsEventStore()
        service_name = getattr(self, "service_name", "auto-kr")
        store.finish_run(
            service=service_name,
            cycle_id=cycle_id,
            status=status,
            scanned_count=summary.get("scan_count", 0),
            analyzed_count=summary.get("analyze_count", 0),
            buy_count=summary.get("buys", 0),
            sell_count=summary.get("sells", 0),
            warning_count=summary.get("warning_count", 0),
            error_count=summary.get("error_count", len(summary.get("errors", []))),
            summary=summary,
        )
        log_event(
            logger,
            logging.INFO if status == "success" else logging.WARNING,
            f"{cycle_type}_finished",
            f"{cycle_type} finished: {status}",
            cycle_id=cycle_id,
            service=service_name,
            status=status,
            **summary,
        )

    def run_daily_cycle(self) -> Dict:
        """장 마감 후 일일 마무리.

        에퀴티 스냅샷, PnL 기록, 일일 요약 전송, 웹 데이터 export.
        매수/매도는 장중 모니터링(run_intraday_monitor)에서 실시간 처리됨.

        Returns:
            일일 결과 요약
        """
        cycle_id = self._start_run("daily_cycle")
        logger.info("=== 일일 마무리 시작 (%s) ===", date.today())

        result = {
            "date": date.today().isoformat(),
            "errors": [],
            "warning_count": 0,
            "error_count": 0,
        }

        # ── 에퀴티 스냅샷 ──
        try:
            self._save_equity_snapshot()
        except Exception as e:
            logger.warning("에퀴티 스냅샷 실패: %s", e)
            result["errors"].append(f"equity: {e}")
            result["warning_count"] += 1
            self._record_ops_event("WARNING", "equity_snapshot_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        # ── 일일 PnL 기록 ──
        try:
            self._record_daily_pnl()
        except Exception as e:
            logger.warning("일일 PnL 기록 실패: %s", e)
            result["warning_count"] += 1
            self._record_ops_event("WARNING", "daily_pnl_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        # ── 일일 요약 전송 ──
        try:
            self.evaluator.daily_summary(optimizer_status=self._optimizer_status)
        except Exception as e:
            logger.warning("일일 요약 전송 실패: %s", e)
            result["warning_count"] += 1
            self._record_ops_event("WARNING", "daily_summary_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

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
            result["warning_count"] += 1
            self._record_ops_event("WARNING", "dashboard_export_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        # 내일 스캔을 위해 캐시 초기화
        self._daily_candidates = []
        self._daily_scan_date = None

        logger.info("=== 일일 마무리 완료 ===")
        self._finish_run("daily_cycle", cycle_id, "success" if not result["errors"] else "warning", result)
        return result

    def run_morning_scan(self) -> int:
        """장 시작 시 유니버스 스캔 + 후보 캐싱.

        매일 1회 실행. 후보 종목을 분석하고 캐시에 저장한다.
        장중 모니터링에서 이 캐시를 사용하여 매수를 시도한다.

        Returns:
            스캔된 후보 종목 수
        """
        cycle_id = self._start_run("morning_scan")
        today = date.today()
        if self._daily_scan_date == today:
            logger.info("오늘 스캔 이미 완료 — 스킵")
            self._finish_run("morning_scan", cycle_id, "skipped", {"scan_count": len(self._daily_candidates)})
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
            self._record_ops_event("WARNING", "optimizer_apply_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        # 유니버스 스캔
        held = set(pos["ticker"] for pos in self.tracker.get_all_open())
        candidates = self.universe.select_universe(held_tickers=held)

        if not candidates:
            logger.info("매수 후보 없음")
            self._daily_candidates = []
            self._daily_scan_date = today
            self._record_ops_event("INFO", "no_buy_candidates", "매수 후보 없음", cycle_id=cycle_id, status="empty")
            try:
                open_count = len(self.tracker.get_all_open())
                chat_id = self.config.auto_trade_chat_id
                if chat_id:
                    from bot.telegram import send_message
                    send_message(
                        f"📋 <b>[{self.config.bot_label}] 매수 후보 없음</b>\n"
                        f"기존 보유 {open_count}종목 모니터링 중",
                        chat_id=chat_id,
                        bot_token=self.config.bot_token or None,
                    )
            except Exception:
                pass
            self._finish_run("morning_scan", cycle_id, "success", {"scan_count": 0, "analyze_count": 0})
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
            self._record_ops_event("WARNING", "scan_summary_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        self._finish_run(
            "morning_scan",
            cycle_id,
            "success",
            {"scan_count": len(candidates), "analyze_count": len(self._daily_candidates)},
        )
        return len(self._daily_candidates)

    def run_intraday_monitor(self) -> Dict:
        """장중 실시간 모니터링 — 매수 + 매도.

        1. 캐시된 후보 종목 중 매수 조건 충족 시 매수
        2. 보유 종목 손절/목표가 도달 시 매도

        Returns:
            {"buys": int, "sells": int}
        """
        cycle_id = self._start_run("intraday_monitor")
        result = {"buys": 0, "sells": 0, "warning_count": 0, "error_count": 0}

        if not self._daily_candidates and self._daily_scan_date != date.today():
            logger.info("후보 캐시 없음 — 장중 재시작 복구를 위해 1회 재스캔")
            try:
                self.run_morning_scan()
            except Exception as e:
                logger.warning("장중 재스캔 실패: %s", e)
                result["warning_count"] += 1
                self._record_ops_event(
                    "WARNING",
                    "intraday_rescan_failed",
                    str(e),
                    cycle_id=cycle_id,
                    error_type=type(e).__name__,
                )

        logger.info("장중 모니터링 시작 (%d 보유, %d 후보)",
                    len(self.tracker.get_all_open()), len(self._daily_candidates))

        # ── 보유 종목 매도 체크 ──
        open_positions = self.tracker.get_all_open()
        if open_positions:
            try:
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
                            self._record_ops_event(
                                "INFO",
                                "sell_executed",
                                f"{order.ticker} sell executed",
                                cycle_id=cycle_id,
                                ticker=order.ticker,
                                order_id=getattr(order, "order_id", None),
                                status=order.status,
                            )
                            _entry_date = decision["position"].get("entry_date", "")
                            try:
                                _holding_days = (
                                    (date.today() - date.fromisoformat(_entry_date)).days
                                    if _entry_date else None
                                )
                            except (ValueError, TypeError):
                                _holding_days = None
                            self.evaluator.send_trade_notification(
                                side="sell",
                                name=order.name,
                                ticker=order.ticker,
                                quantity=order.quantity,
                                price=order.price,
                                reason=decision["recommendation"].get("action", ""),
                                pnl_pct=decision["recommendation"].get("pnl_pct"),
                                pnl_amount=decision["recommendation"].get("pnl_amount"),
                                holding_days=_holding_days,
                            )
                    except Exception as e:
                        logger.error(
                            "매도 실행 실패: %s(%s) — %s",
                            decision["stock_data"]["name"],
                            decision["stock_data"]["ticker"], e,
                        )
                        result["error_count"] += 1
                        self._record_ops_event(
                            "ERROR",
                            "sell_execution_failed",
                            str(e),
                            cycle_id=cycle_id,
                            ticker=decision["stock_data"].get("ticker"),
                            error_type=type(e).__name__,
                        )
            except Exception as e:
                logger.error("보유 종목 매도 분석 실패 — 매수 체크로 진행: %s", e, exc_info=True)
                result["error_count"] += 1
                self._record_ops_event("ERROR", "sell_analysis_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

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
                if not buy_decisions:
                    self._log_buy_rejection_summary(remaining, cycle_id=cycle_id)
                for decision in buy_decisions:
                    try:
                        order = self.executor.execute_buy(
                            decision["stock_data"],
                            decision["recommendation"],
                        )
                        if order and order.status in ("filled", "simulated"):
                            result["buys"] += 1
                            self._record_ops_event(
                                "INFO",
                                "buy_executed",
                                f"{order.ticker} buy executed",
                                cycle_id=cycle_id,
                                ticker=order.ticker,
                                order_id=getattr(order, "order_id", None),
                                status=order.status,
                            )
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
                                details={
                                    "stop_loss": decision["recommendation"].get("stop_loss", 0),
                                    "target1": decision["recommendation"].get("target1", 0),
                                    "target2": decision["recommendation"].get("target2", 0),
                                    "weight_pct": decision["recommendation"].get(
                                        "weight_pct", self.config.target_weight_pct
                                    ),
                                    "regime": decision["stock_data"].get("market_regime", ""),
                                },
                            )
                            # 매수 완료된 종목은 캐시에서 제거
                            self._daily_candidates = [
                                c for c in self._daily_candidates
                                if c.get("ticker") != order.ticker
                            ]
                    except Exception as e:
                        logger.error("매수 실행 실패: %s", e)
                        result["error_count"] += 1
                        self._record_ops_event(
                            "ERROR",
                            "buy_execution_failed",
                            str(e),
                            cycle_id=cycle_id,
                            ticker=decision["stock_data"].get("ticker"),
                            error_type=type(e).__name__,
                        )

        logger.info("장중 모니터링: 매수 %d건, 매도 %d건",
                    result["buys"], result["sells"])

        self._finish_run("intraday_monitor", cycle_id, "success" if result["error_count"] == 0 else "warning", result)
        return result

    def run_weekly_evaluation(self) -> Dict:
        """주간 성과 평가를 실행한다."""
        cycle_id = self._start_run("weekly_evaluation")
        logger.info("=== 주간 성과 평가 시작 ===")

        # 최근 매도 거래의 결과를 optimizer에 기록
        try:
            self._update_optimizer_with_closed_trades()
        except Exception as e:
            logger.warning("optimizer 거래 결과 갱신 실패: %s", e)
            self._record_ops_event("WARNING", "weekly_optimizer_update_failed", str(e), cycle_id=cycle_id, error_type=type(e).__name__)

        report = self.evaluator.weekly_report()
        self._finish_run("weekly_evaluation", cycle_id, "success", {})
        return report

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
                    _entry_date = decision["position"].get("entry_date", "")
                    try:
                        _holding_days = (
                            (date.today() - date.fromisoformat(_entry_date)).days
                            if _entry_date else None
                        )
                    except (ValueError, TypeError):
                        _holding_days = None
                    self.evaluator.send_trade_notification(
                        side="sell",
                        name=order.name,
                        ticker=order.ticker,
                        quantity=order.quantity,
                        price=order.price,
                        reason=decision["recommendation"].get("action", ""),
                        pnl_pct=decision["recommendation"].get("pnl_pct"),
                        pnl_amount=decision["recommendation"].get("pnl_amount"),
                        holding_days=_holding_days,
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
            self._log_buy_rejection_summary(analyzed)
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
                        details={
                            "stop_loss": decision["recommendation"].get("stop_loss", 0),
                            "target1": decision["recommendation"].get("target1", 0),
                            "target2": decision["recommendation"].get("target2", 0),
                            "weight_pct": decision["recommendation"].get(
                                "weight_pct", self.config.target_weight_pct
                            ),
                            "regime": decision["stock_data"].get("market_regime", ""),
                        },
                    )
            except Exception as e:
                logger.error("매수 실행 실패: %s", e)

        phase_result["buys"] = buy_count
        return phase_result

    def _log_buy_rejection_summary(self, analyzed_stocks: List[Dict], cycle_id: str = "") -> None:
        """매수 실패 사유를 집계해 로그와 ops 이벤트에 남긴다."""
        if not analyzed_stocks:
            return

        open_positions = self.tracker.get_all_open()
        reason_counts = Counter()

        for stock in analyzed_stocks:
            recommendation = self.trade_rule.should_buy(stock, open_positions)
            if recommendation.get("recommend"):
                reason = "__recommended__"
            else:
                reason = recommendation.get("reason") or "사유 없음"
            reason_counts[reason] += 1

        rejected = [(reason, count) for reason, count in reason_counts.items() if reason != "__recommended__"]
        if not rejected:
            return

        rejected.sort(key=lambda item: (-item[1], item[0]))
        top_reasons = rejected[:5]
        summary = ", ".join(f"{reason}={count}" for reason, count in top_reasons)

        logger.info("매수 탈락 사유 상위: %s", summary)
        self._record_ops_event(
            "INFO",
            "buy_rejection_summary",
            summary,
            cycle_id=cycle_id,
            analyzed_count=len(analyzed_stocks),
            reasons=dict(top_reasons),
        )

    def _save_equity_snapshot(self) -> None:
        """에퀴티 스냅샷을 저장한다."""
        open_positions = self.tracker.get_all_open()

        # dry_run이 아닐 때만 API 평가 사용 (dry_run에서는 모의 계좌 잔고가 가상 자산과 다름)
        if not self.config.dry_run and open_positions and self.executor.portfolio:
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

        # dry_run 또는 포지션 없음 또는 평가 실패: 마크-투-마켓 가상 에퀴티 계산
        unrealized_pnl = 0
        invested = 0
        for pos in open_positions:
            entry = pos.get("entry_price", 0)
            current = pos.get("highest_close") or entry  # 최근 최고가를 현재가 근사값으로 사용
            weight = pos.get("weight_pct", 0)
            position_value = DRY_RUN_VIRTUAL_ASSET * weight / 100
            invested += position_value
            if entry > 0:
                unrealized_pnl += position_value * (current - entry) / entry
        total_equity = DRY_RUN_VIRTUAL_ASSET + unrealized_pnl
        self.state.save_equity_snapshot(
            total_equity=total_equity,
            invested=invested,
            cash=total_equity - invested,
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
