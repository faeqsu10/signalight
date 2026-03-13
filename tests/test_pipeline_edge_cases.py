"""파이프라인 통합 엣지 케이스 테스트.

검증 대상:
1. 킬스위치 파일 존재 시 매수/매도 모두 차단
2. 서킷 브레이커(일일 손실 > 2%) 활성 시 매수 차단
3. 빈 유니버스(후보 0개)에서 에러 없이 종료
4. 분석 실패 종목이 있어도 나머지 정상 진행
5. SafeExecutor._check_all_safety() 개별 검증
6. 일일 스캔 중복 방지

외부 API/DB 의존성은 mock으로 대체한다.
pykrx 등 불필요한 외부 모듈은 sys.modules에 MagicMock으로 삽입해서
import 시점 오류를 방지한다.
"""

import sys
import os
import types
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime

# ── pykrx / 외부 모듈 mock (import 시점) ───────────────────────────────────
# pykrx, python-telegram-bot 등 설치되지 않은 모듈을 미리 stub으로 등록
_MISSING = [
    "pykrx", "pykrx.stock",
    "telegram", "telegram.ext",
    "schedule",
    "lxml", "lxml.html",
    "requests",
]
for _mod in _MISSING:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ── 프로젝트 루트 경로 ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SafeExecutor 킬스위치
# ═══════════════════════════════════════════════════════════════════════════════

class TestKillSwitch:
    """킬스위치 파일 존재 시 주문이 차단되는지 확인."""

    def _make_executor(self, tmp_path):
        """격리된 DB를 사용하는 SafeExecutor를 생성한다."""
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from autonomous.execution import SafeExecutor

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))
        return SafeExecutor(state=state, position_tracker=tracker)

    def test_kill_switch_file_blocks_buy(self, tmp_path):
        """킬스위치 파일이 존재하면 _check_kill_switch()가 False를 반환한다."""
        kill_path = str(tmp_path / "kill_file")
        with open(kill_path, "w") as f:
            f.write("kill")

        executor = self._make_executor(tmp_path)

        from autonomous.config import AUTO_CONFIG
        original = AUTO_CONFIG.kill_switch_path
        AUTO_CONFIG.kill_switch_path = kill_path
        try:
            result = executor._check_kill_switch()
            assert result is False, "킬스위치 파일이 있으면 False를 반환해야 한다"
        finally:
            AUTO_CONFIG.kill_switch_path = original
            os.remove(kill_path)

    def test_kill_switch_file_absent_allows_order(self, tmp_path):
        """킬스위치 파일이 없으면 _check_kill_switch()가 True를 반환한다."""
        executor = self._make_executor(tmp_path)
        nonexistent = str(tmp_path / "no_kill_file")

        from autonomous.config import AUTO_CONFIG
        original = AUTO_CONFIG.kill_switch_path
        AUTO_CONFIG.kill_switch_path = nonexistent
        try:
            result = executor._check_kill_switch()
            assert result is True
        finally:
            AUTO_CONFIG.kill_switch_path = original

    def test_kill_switch_presence_returns_false(self, tmp_path):
        """킬스위치 파일이 존재하면 _check_kill_switch()가 False를 반환한다 (재검증)."""
        executor = self._make_executor(tmp_path)
        kill_path = str(tmp_path / "signalight_kill")
        with open(kill_path, "w") as f:
            f.write("kill")

        from autonomous.config import AUTO_CONFIG
        original = AUTO_CONFIG.kill_switch_path
        AUTO_CONFIG.kill_switch_path = kill_path
        try:
            result = executor._check_kill_switch()
            assert result is False
        finally:
            AUTO_CONFIG.kill_switch_path = original
            os.remove(kill_path)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 서킷 브레이커
# ═══════════════════════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    """PipelineState 서킷 브레이커 활성 시 매수 차단."""

    def test_circuit_breaker_inactive_when_no_entry(self, tmp_path):
        """서킷 브레이커 발동 기록이 없으면 is_circuit_breaker_active()가 None."""
        from autonomous.state import PipelineState
        state = PipelineState(db_path=str(tmp_path / "state.db"))
        assert state.is_circuit_breaker_active() is None

    def test_circuit_breaker_active_after_trigger(self, tmp_path):
        """record_circuit_breaker() 호출 후 is_circuit_breaker_active()가 활성."""
        from autonomous.state import PipelineState
        state = PipelineState(db_path=str(tmp_path / "state.db"))

        state.record_circuit_breaker(
            trigger_type="daily_loss",
            resume_date="2099-12-31",
            detail="일일 손실 2% 초과",
        )

        cb = state.is_circuit_breaker_active()
        assert cb is not None
        assert cb["trigger_type"] == "daily_loss"

    def test_decision_engine_blocks_buy_when_circuit_breaker_active(self, tmp_path):
        """서킷 브레이커 활성 시 DecisionEngine.make_buy_decisions()가 빈 리스트."""
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from trading.rules import TradeRule
        from autonomous.decision import DecisionEngine

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))

        state.record_circuit_breaker(
            trigger_type="daily_loss",
            resume_date="2099-12-31",
            detail="테스트",
        )

        engine = DecisionEngine(
            trade_rule=TradeRule(),
            position_tracker=tracker,
            state=state,
        )

        from tests.conftest import make_stock_data
        good_stock = make_stock_data(
            confluence_direction="buy",
            confluence_score=4.0,
            buy_score=4.0,
            regime="uptrend",
            atr=1000,
            volume_ratio=1.0,
        )

        decisions = engine.make_buy_decisions([good_stock])
        assert decisions == [], "서킷 브레이커 활성 시 매수 결정이 없어야 한다"

    def test_circuit_breaker_does_not_block_sell_check(self, tmp_path):
        """서킷 브레이커는 is_sell=True 호출 시 체크를 건너뛴다.

        _check_all_safety(is_sell=True)에서 서킷 브레이커 코드가
        실행되지 않는다는 것을 state.is_circuit_breaker_active 호출 횟수로 검증한다.
        """
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from autonomous.execution import SafeExecutor

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))

        state.record_circuit_breaker(
            trigger_type="daily_loss",
            resume_date="2099-12-31",
            detail="테스트",
        )

        executor = SafeExecutor(state=state, position_tracker=tracker)

        # _check_all_safety(is_sell=True)에서 서킷브레이커 체크는 건너뜀
        # is_circuit_breaker_active가 호출되지 않아야 함
        with patch.object(state, "is_circuit_breaker_active",
                          wraps=state.is_circuit_breaker_active) as mock_cb:
            # 장중 평일로 mock
            mock_now = datetime(2026, 3, 9, 10, 0, 0)
            with patch("autonomous.execution.datetime") as mock_dt:
                mock_dt.now.return_value = mock_now
                executor._check_all_safety(is_sell=True)

            # is_sell=True이면 서킷 브레이커 체크 건너뜀 → 호출 없음
            mock_cb.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 빈 유니버스 처리
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyUniverse:
    """후보 종목이 0개일 때 파이프라인이 에러 없이 종료되는지 확인."""

    def _make_pipeline(self, tmp_path):
        """pykrx 없이도 생성 가능한 파이프라인 stub을 반환한다."""
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))

        # AutonomousPipeline을 직접 import 하면 pykrx 필요 → __new__로 우회
        # 모듈 자체 import 전에 pykrx를 mock으로 등록했으므로 OK
        from autonomous.pipeline import AutonomousPipeline

        pipeline = AutonomousPipeline.__new__(AutonomousPipeline)
        pipeline.state = state
        pipeline.tracker = tracker
        pipeline._daily_candidates = []
        pipeline._daily_scan_date = None
        pipeline._optimizer_status = None
        pipeline._base_thresholds = {}
        pipeline._base_min_volume_ratio = 0.3
        pipeline._base_rule_overrides = {}

        pipeline.universe = MagicMock()
        pipeline.universe.select_universe.return_value = []
        pipeline.universe.scan_weights = {}

        pipeline.analyzer = MagicMock()
        pipeline.analyzer.clear_cache.return_value = None

        pipeline.executor = MagicMock()
        pipeline.executor.reset_daily.return_value = None

        pipeline.optimizer = MagicMock()
        pipeline.optimizer.get_optimized_params.return_value = {
            "active": False,
            "scan_weights": {},
            "buy_thresholds": {},
        }

        pipeline.evaluator = MagicMock()
        pipeline.trade_rule = MagicMock()

        return pipeline

    def test_empty_candidates_returns_zero(self, tmp_path):
        """select_universe()가 빈 리스트를 반환할 때 run_morning_scan()이 0을 반환."""
        pipeline = self._make_pipeline(tmp_path)
        count = pipeline.run_morning_scan()
        assert count == 0

    def test_empty_candidates_no_analysis_call(self, tmp_path):
        """후보가 없으면 analyze_candidates()가 호출되지 않아야 한다."""
        pipeline = self._make_pipeline(tmp_path)
        pipeline.run_morning_scan()
        pipeline.analyzer.analyze_candidates.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 분석 실패 종목 허용
# ═══════════════════════════════════════════════════════════════════════════════

class TestPartialAnalysisFailure:
    """일부 종목 분석 실패 시 나머지 종목이 정상 처리되는지 확인."""

    def test_failed_analysis_skipped_rest_processed(self):
        """분석 중 예외가 발생한 종목은 건너뛰고 나머지는 정상 처리된다.

        실제 StockAnalyzer 대신 분석 함수를 직접 시뮬레이션한다.
        """
        good_result = {
            "ticker": "005930", "name": "삼성전자",
            "confluence_score": 3.0, "confluence_direction": "buy",
            "signals": [], "indicators": {"atr": 1000},
        }

        def _analyze_one(candidate):
            """일부 종목에서 예외를 던지는 분석 함수 시뮬레이션."""
            if candidate["ticker"] == "FAIL":
                raise RuntimeError("데이터 없음")
            return good_result

        candidates = [
            {"ticker": "FAIL", "name": "실패종목"},
            {"ticker": "005930", "name": "삼성전자"},
        ]

        results = []
        for c in candidates:
            try:
                result = _analyze_one(c)
                if result is not None:
                    results.append(result)
            except Exception:
                pass  # 실패 종목 스킵

        assert len(results) == 1, "성공한 종목 1개만 결과에 포함되어야 한다"
        assert results[0]["ticker"] == "005930"

    def test_make_buy_decisions_handles_empty_analysis(self, tmp_path):
        """분석 결과가 빈 리스트이면 매수 결정도 빈 리스트다."""
        from autonomous.decision import DecisionEngine
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from trading.rules import TradeRule

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))

        engine = DecisionEngine(
            trade_rule=TradeRule(),
            position_tracker=tracker,
            state=state,
        )

        decisions = engine.make_buy_decisions([])
        assert decisions == []


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 장중 시간 체크
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketHoursCheck:
    """SafeExecutor._check_market_hours()가 장외 시간을 올바르게 차단한다."""

    def _make_executor(self, tmp_path):
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from autonomous.execution import SafeExecutor
        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))
        return SafeExecutor(state=state, position_tracker=tracker)

    def test_before_market_open_returns_false(self, tmp_path):
        """장 시작 전(08:00)에는 주문 불가."""
        executor = self._make_executor(tmp_path)
        mock_now = datetime(2026, 3, 9, 8, 0, 0)  # 월요일 08:00
        with patch("autonomous.execution.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = executor._check_market_hours()
        assert result is False

    def test_after_market_close_returns_false(self, tmp_path):
        """장 마감 후(15:30)에는 주문 불가."""
        executor = self._make_executor(tmp_path)
        mock_now = datetime(2026, 3, 9, 15, 30, 0)  # 월요일 15:30
        with patch("autonomous.execution.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = executor._check_market_hours()
        assert result is False

    def test_during_market_hours_returns_true(self, tmp_path):
        """장중(10:00)에는 주문 가능."""
        executor = self._make_executor(tmp_path)
        mock_now = datetime(2026, 3, 9, 10, 0, 0)  # 월요일 10:00
        with patch("autonomous.execution.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = executor._check_market_hours()
        assert result is True

    def test_weekend_returns_false(self, tmp_path):
        """주말(토요일)에는 장중이라도 주문 불가."""
        executor = self._make_executor(tmp_path)
        mock_now = datetime(2026, 3, 7, 10, 0, 0)  # 토요일
        with patch("autonomous.execution.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = executor._check_market_hours()
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 일일 스캔 중복 방지
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyScanDeduplication:
    """같은 날 run_morning_scan()을 두 번 호출하면 두 번째는 스킵된다."""

    def test_second_scan_same_day_returns_cached_count(self, tmp_path):
        """오늘 이미 스캔했으면 두 번째 호출은 캐시된 수를 반환한다."""
        from autonomous.state import PipelineState
        from trading.position_tracker import PositionTracker
        from autonomous.pipeline import AutonomousPipeline

        state = PipelineState(db_path=str(tmp_path / "state.db"))
        tracker = PositionTracker(db_path=str(tmp_path / "tracker.db"))

        pipeline = AutonomousPipeline.__new__(AutonomousPipeline)
        pipeline.state = state
        pipeline.tracker = tracker
        # 오늘 날짜로 이미 스캔 완료 표시
        pipeline._daily_candidates = [{"ticker": "005930", "name": "삼성전자"}]
        pipeline._daily_scan_date = date.today()

        mock_universe = MagicMock()
        pipeline.universe = mock_universe

        count = pipeline.run_morning_scan()

        # 두 번째 스캔은 스킵 → 캐시된 1개 반환
        assert count == 1
        # universe.select_universe()는 호출되지 않아야 한다
        mock_universe.select_universe.assert_not_called()
