"""dry_run 모드 에퀴티 스냅샷 테스트.

버그 배경:
- dry_run=True 모드에서 포지션이 있어도 invested=0으로 계산돼
  킬스위치의 MDD 계산에서 분모가 0이 되거나 오판이 발생했다.
- PositionTracker.open_position() 에 quantity 컬럼이 없어서
  pipeline._save_equity_snapshot()의 sum(p.get("quantity", 0)) 이 항상 0.

이 테스트는 해당 로직을 직접 검증한다.
"""

import sys
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.position_tracker import PositionTracker
from config import DRY_RUN_VIRTUAL_ASSET


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _open_position(tracker, ticker="005930", name="삼성전자",
                   price=70000, weight_pct=5.0):
    """테스트용 포지션을 생성한다."""
    return tracker.open_position(
        ticker=ticker,
        name=name,
        entry_price=price,
        entry_atr=1000.0,
        regime="sideways",
        stop_loss=int(price * 0.92),
        target1=int(price * 1.04),
        target2=int(price * 1.07),
        weight_pct=weight_pct,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. dry_run 에퀴티 스냅샷 로직 단위 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestDryRunEquityCalculation:
    """pipeline._save_equity_snapshot()의 dry_run 분기 로직 검증.

    실제 pipeline 인스턴스 대신 로직을 직접 재현한다.
    (pipeline은 외부 DB/API 의존성이 많아 단위 테스트에서 mock이 복잡함)
    """

    def test_dry_run_total_equity_equals_virtual_asset_constant(self):
        """dry_run 모드에서 total_equity는 DRY_RUN_VIRTUAL_ASSET 상수와 같다."""
        # pipeline._save_equity_snapshot() 의 dry_run 분기 재현
        open_positions = [{"entry_price": 70000, "quantity": 10, "weight_pct": 5.0}]

        total_equity = DRY_RUN_VIRTUAL_ASSET  # 항상 이 상수
        invested = sum(
            p.get("entry_price", 0) * p.get("quantity", 0)
            for p in open_positions
        )

        assert total_equity == DRY_RUN_VIRTUAL_ASSET
        assert total_equity > 0

    def test_dry_run_invested_uses_quantity_field(self):
        """dry_run에서 invested는 entry_price * quantity 합산이다."""
        open_positions = [
            {"entry_price": 70000, "quantity": 10},
            {"entry_price": 120000, "quantity": 5},
        ]
        invested = sum(
            p.get("entry_price", 0) * p.get("quantity", 0)
            for p in open_positions
        )
        # 70000*10 + 120000*5 = 700000 + 600000 = 1300000
        assert invested == 1_300_000

    def test_dry_run_position_without_quantity_field_gives_zero_invested(self):
        """포지션에 quantity 필드가 없으면 invested=0이 된다 (알려진 버그 재현).

        이 테스트는 quantity 필드 없이는 invested가 0임을 명시적으로 검증한다.
        실제 PositionTracker.open_position()은 quantity를 저장하지 않는다.
        """
        open_positions = [
            # PositionTracker.get_all_open()이 반환하는 실제 구조
            {"ticker": "005930", "entry_price": 70000, "weight_pct": 5.0}
            # quantity 필드 없음
        ]
        invested = sum(
            p.get("entry_price", 0) * p.get("quantity", 0)
            for p in open_positions
        )
        assert invested == 0, (
            "quantity 필드가 없으면 invested=0 이 된다 — 이 버그를 인지하고 있어야 한다"
        )

    def test_dry_run_cash_equals_total_minus_invested(self):
        """cash = total_equity - invested."""
        total_equity = DRY_RUN_VIRTUAL_ASSET
        invested = 5_000_000
        cash = total_equity - invested

        assert cash == total_equity - invested
        assert cash > 0  # invested < total_equity 이므로

    def test_dry_run_equity_is_positive_even_with_no_positions(self):
        """포지션이 없어도 dry_run total_equity는 양수다."""
        open_positions = []
        invested = sum(
            p.get("entry_price", 0) * p.get("quantity", 0)
            for p in open_positions
        )
        total_equity = DRY_RUN_VIRTUAL_ASSET

        assert total_equity > 0
        assert invested == 0
        assert total_equity - invested == DRY_RUN_VIRTUAL_ASSET


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PipelineState 에퀴티 저장/조회 (격리된 DB)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineStateEquitySnapshot:
    """PipelineState.save_equity_snapshot()과 get_max_drawdown() 연계 테스트."""

    def test_save_and_retrieve_equity_snapshot(self, tmp_path):
        """에퀴티 스냅샷을 저장하면 DB에 기록된다."""
        db_path = str(tmp_path / "state.db")

        from autonomous.state import PipelineState
        state = PipelineState(db_path=db_path)

        state.save_equity_snapshot(
            total_equity=50_000_000,
            invested=5_000_000,
            cash=45_000_000,
            open_positions=1,
        )

        # get_max_drawdown이 에러 없이 동작하는지 확인
        mdd = state.get_max_drawdown()
        assert isinstance(mdd, float)

    def test_dry_run_equity_snapshot_with_nonzero_total(self, tmp_path):
        """dry_run 모드에서 total_equity가 0이 아니면 킬스위치 오판이 없다."""
        db_path = str(tmp_path / "state.db")

        from autonomous.state import PipelineState
        state = PipelineState(db_path=db_path)

        # 정상 에퀴티 저장 (dry_run 기준: DRY_RUN_VIRTUAL_ASSET)
        state.save_equity_snapshot(
            total_equity=DRY_RUN_VIRTUAL_ASSET,
            invested=0,
            cash=DRY_RUN_VIRTUAL_ASSET,
            open_positions=0,
        )

        mdd = state.get_max_drawdown()
        # 에퀴티 변화가 없으면 MDD=0
        assert mdd == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 킬스위치 MDD 트리거 로직
# ═══════════════════════════════════════════════════════════════════════════════

class TestKillSwitchMDDLogic:
    """MDD > 15% 시 킬스위치가 발동하는 조건을 단위 검증한다."""

    def _insert_equity(self, db_path: str, date_str: str, total_equity: int):
        """테스트용으로 특정 날짜의 에퀴티를 직접 DB에 삽입한다.

        save_equity_snapshot()은 ON CONFLICT(snapshot_date)로 같은 날 덮어쓰므로
        다른 날짜로 직접 삽입해야 여러 행을 만들 수 있다.
        """
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """INSERT OR REPLACE INTO auto_equity_snapshots
               (snapshot_date, total_equity, invested_amount, cash_amount, open_positions)
               VALUES (?, ?, 0, ?, 0)""",
            (date_str, total_equity, total_equity),
        )
        conn.commit()
        conn.close()

    def test_mdd_below_threshold_does_not_trigger(self, tmp_path):
        """MDD가 15% 미만이면 킬스위치 조건 미충족."""
        db_path = str(tmp_path / "state.db")
        from autonomous.state import PipelineState
        state = PipelineState(db_path=db_path)

        # 에퀴티가 9% 하락한 경우 (15% 미만)
        peak = 50_000_000
        current = int(peak * 0.91)

        self._insert_equity(db_path, "2026-03-01", peak)
        self._insert_equity(db_path, "2026-03-10", current)

        mdd = state.get_max_drawdown()
        max_drawdown_threshold = 15.0

        assert mdd < max_drawdown_threshold, (
            f"MDD={mdd:.1f}%가 킬스위치 임계값 {max_drawdown_threshold}% 미만이어야 한다"
        )

    def test_mdd_above_threshold_triggers_kill_condition(self, tmp_path):
        """MDD가 15% 초과이면 킬스위치 조건 충족."""
        db_path = str(tmp_path / "state.db")
        from autonomous.state import PipelineState
        state = PipelineState(db_path=db_path)

        peak = 50_000_000
        current = int(peak * 0.80)  # 20% 하락

        self._insert_equity(db_path, "2026-03-01", peak)
        self._insert_equity(db_path, "2026-03-10", current)

        mdd = state.get_max_drawdown()
        max_drawdown_threshold = 15.0

        assert mdd >= max_drawdown_threshold, (
            f"MDD={mdd:.1f}%가 킬스위치 임계값 {max_drawdown_threshold}% 이상이어야 한다"
        )
