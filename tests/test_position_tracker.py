"""PositionTracker DB 분리 테스트.

버그 배경:
- US/KR 파이프라인이 같은 PositionTracker DB를 공유하면
  US 파이프라인이 KR 종목을 분석 시도 → 404 에러 발생.
- PositionTracker(db_path="kr.db")와 PositionTracker(db_path="us.db")가
  완전히 독립된 DB를 사용하는지 검증한다.
- 기본 db_path="" 시 KR DB(signalight.db)를 사용하는 하위 호환 확인.
"""

import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.position_tracker import PositionTracker, DB_PATH


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DB 분리 — KR/US 독립성
# ═══════════════════════════════════════════════════════════════════════════════

class TestDBIsolation:
    """KR tracker와 US tracker가 서로 다른 DB를 사용하는지 확인."""

    def test_kr_and_us_trackers_use_different_db_paths(self, tmp_path):
        """KR tracker와 US tracker의 _db_path가 다르다."""
        kr_db = str(tmp_path / "kr.db")
        us_db = str(tmp_path / "us.db")

        kr = PositionTracker(db_path=kr_db)
        us = PositionTracker(db_path=us_db)

        assert kr._db_path != us._db_path

    def test_position_opened_in_kr_not_visible_in_us(self, tmp_path):
        """KR에서 open한 포지션이 US tracker에서 보이지 않는다."""
        kr_db = str(tmp_path / "kr.db")
        us_db = str(tmp_path / "us.db")

        kr = PositionTracker(db_path=kr_db)
        us = PositionTracker(db_path=us_db)

        kr.open_position(
            ticker="005930",
            name="삼성전자",
            entry_price=70000,
            entry_atr=1000.0,
            regime="sideways",
            stop_loss=68000,
            target1=72000,
            target2=74000,
            weight_pct=5.0,
        )

        # US tracker에서는 보이지 않아야 한다
        pos_in_us = us.get_position("005930")
        assert pos_in_us is None, (
            "KR에서 open한 포지션이 US tracker에 보이면 안 된다"
        )

    def test_position_opened_in_us_not_visible_in_kr(self, tmp_path):
        """US에서 open한 포지션이 KR tracker에서 보이지 않는다."""
        kr_db = str(tmp_path / "kr.db")
        us_db = str(tmp_path / "us.db")

        kr = PositionTracker(db_path=kr_db)
        us = PositionTracker(db_path=us_db)

        us.open_position(
            ticker="AAPL",
            name="Apple",
            entry_price=180,
            entry_atr=3.0,
            regime="uptrend",
            stop_loss=172,
            target1=185,
            target2=192,
            weight_pct=5.0,
        )

        pos_in_kr = kr.get_position("AAPL")
        assert pos_in_kr is None, (
            "US에서 open한 포지션이 KR tracker에 보이면 안 된다"
        )

    def test_get_all_open_returns_only_own_positions(self, tmp_path):
        """get_all_open()은 각자 DB의 포지션만 반환한다."""
        kr_db = str(tmp_path / "kr.db")
        us_db = str(tmp_path / "us.db")

        kr = PositionTracker(db_path=kr_db)
        us = PositionTracker(db_path=us_db)

        kr.open_position("005930", "삼성전자", 70000, 1000.0,
                         "sideways", 68000, 72000, 74000, 5.0)
        kr.open_position("000660", "SK하이닉스", 120000, 2000.0,
                         "sideways", 115000, 125000, 130000, 5.0)

        us.open_position("AAPL", "Apple", 180, 3.0,
                         "uptrend", 172, 185, 192, 5.0)

        kr_all = kr.get_all_open()
        us_all = us.get_all_open()

        assert len(kr_all) == 2
        assert len(us_all) == 1
        assert all(p["ticker"] in ("005930", "000660") for p in kr_all)
        assert us_all[0]["ticker"] == "AAPL"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 기본 db_path 하위 호환
# ═══════════════════════════════════════════════════════════════════════════════

class TestDefaultDBPath:
    """db_path 미지정 시 KR DB(signalight.db)가 사용되는지 확인."""

    def test_default_tracker_uses_kr_db_path(self):
        """db_path="" 인 PositionTracker의 _db_path가 빈 문자열이다
        (빈 문자열이면 내부에서 KR DB_PATH 사용)."""
        tracker = PositionTracker()  # db_path 미지정
        assert tracker._db_path == ""

    def test_module_level_db_path_is_kr_storage(self):
        """모듈 수준 DB_PATH가 storage/signalight.db를 가리킨다."""
        assert "signalight.db" in DB_PATH
        assert "storage" in DB_PATH


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CRUD 기본 동작 (격리된 DB)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPositionCRUD:
    """포지션 생성/조회/업데이트/청산 기본 동작을 격리된 DB로 검증."""

    def test_open_position_returns_positive_id(self, tmp_db):
        """open_position()이 양수 ID를 반환한다."""
        tracker = PositionTracker(db_path=tmp_db)
        pos_id = tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        assert pos_id > 0

    def test_get_position_returns_opened_position(self, tmp_db):
        """open 후 get_position()으로 조회하면 해당 포지션을 반환한다."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        pos = tracker.get_position("005930")

        assert pos is not None
        assert pos["ticker"] == "005930"
        assert pos["status"] == "open"
        assert pos["entry_price"] == 70000

    def test_get_position_returns_none_for_unknown_ticker(self, tmp_db):
        """존재하지 않는 종목은 None을 반환한다."""
        tracker = PositionTracker(db_path=tmp_db)
        assert tracker.get_position("UNKNOWN") is None

    def test_close_position_changes_status_to_closed(self, tmp_db):
        """close_position() 후 status가 'closed'로 변경된다."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )

        closed = tracker.close_position("005930", exit_price=72000, exit_reason="target1")

        assert closed is not None
        assert closed["exit_price"] == 72000
        assert closed["exit_reason"] == "target1"
        assert round(closed["pnl_pct"], 1) == round((72000 - 70000) / 70000 * 100, 1)

        # open 포지션 조회 시 없어야 함
        assert tracker.get_position("005930") is None

    def test_close_nonexistent_position_returns_none(self, tmp_db):
        """존재하지 않는 포지션 청산 시 None을 반환한다."""
        tracker = PositionTracker(db_path=tmp_db)
        result = tracker.close_position("NONE", exit_price=0, exit_reason="test")
        assert result is None

    def test_update_phase_increments_correctly(self, tmp_db):
        """update_phase()가 phase를 올바르게 업데이트한다."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        tracker.update_phase("005930", new_phase=2, additional_weight=5.0)

        pos = tracker.get_position("005930")
        assert pos["phase"] == 2
        assert abs(pos["weight_pct"] - 10.0) < 0.01

    def test_update_highest_close_only_increases(self, tmp_db):
        """update_highest_close()는 현재보다 낮은 값으로 갱신되지 않는다."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        tracker.update_highest_close("005930", 75000)
        tracker.update_highest_close("005930", 71000)  # 낮은 값 시도

        pos = tracker.get_position("005930")
        assert pos["highest_close"] == 75000  # 낮은 값으로 갱신되지 않아야 함

    def test_mark_target_hit_sets_flag(self, tmp_db):
        """mark_target_hit() 후 target1_hit=1로 설정된다."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        tracker.mark_target_hit("005930", 1)
        pos = tracker.get_position("005930")
        assert pos["target1_hit"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 성과 요약 (격리된 DB)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceSummary:
    """get_performance_summary()가 올바른 집계 결과를 반환하는지 확인."""

    def test_empty_db_returns_zero_summary(self, tmp_db):
        """거래 이력이 없으면 총거래=0, 승률=0을 반환한다."""
        tracker = PositionTracker(db_path=tmp_db)
        summary = tracker.get_performance_summary()

        assert summary["total_trades"] == 0
        assert summary["win_rate"] == 0

    def test_single_winning_trade_win_rate_100(self, tmp_db):
        """이익 거래 1건이면 승률 100%."""
        tracker = PositionTracker(db_path=tmp_db)
        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        tracker.close_position("005930", exit_price=72000, exit_reason="target1")

        summary = tracker.get_performance_summary()
        assert summary["total_trades"] == 1
        assert summary["win_rate"] == 100.0

    def test_one_win_one_loss_win_rate_50(self, tmp_db):
        """이익 1건 + 손실 1건이면 승률 50%."""
        tracker = PositionTracker(db_path=tmp_db)

        tracker.open_position(
            "005930", "삼성전자", 70000, 1000.0,
            "sideways", 68000, 72000, 74000, 5.0,
        )
        tracker.close_position("005930", exit_price=72000, exit_reason="target1")

        tracker.open_position(
            "000660", "SK하이닉스", 120000, 2000.0,
            "sideways", 115000, 125000, 130000, 5.0,
        )
        tracker.close_position("000660", exit_price=115000, exit_reason="stop_loss")

        summary = tracker.get_performance_summary()
        assert summary["total_trades"] == 2
        assert summary["win_rate"] == 50.0
