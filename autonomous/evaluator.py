"""성과 평가기 — 주간 리포트 + 텔레그램 전송.

PositionTracker와 PipelineState의 데이터를 기반으로
승률, 평균 PnL, 최대 낙폭 등을 계산하고 텔레그램으로 전송한다.
"""

import logging
from datetime import date
from typing import Dict, Optional

from bot.telegram import send_message
from trading.position_tracker import PositionTracker
from autonomous.config import AUTO_CONFIG
from autonomous.state import PipelineState

logger = logging.getLogger("signalight.auto")


class PerformanceEvaluator:
    """성과 평가기."""

    def __init__(
        self,
        state: PipelineState = None,
        position_tracker: PositionTracker = None,
    ):
        self.state = state or PipelineState()
        self.tracker = position_tracker or PositionTracker()

    def weekly_report(self) -> Dict:
        """주간 성과 리포트를 생성하고 텔레그램으로 전송한다."""
        # 성과 데이터 수집
        perf_7d = self.state.get_performance_summary(days=7)
        perf_30d = self.state.get_performance_summary(days=30)
        weekly_pnl = self.state.get_weekly_pnl()
        open_positions = self.tracker.get_all_open()
        recent_trades = self.state.get_recent_trades(days=7)

        # 메시지 생성
        msg = self._format_weekly_report(
            perf_7d, perf_30d, weekly_pnl,
            open_positions, recent_trades,
        )

        # 텔레그램 전송
        chat_id = AUTO_CONFIG.auto_trade_chat_id
        if chat_id:
            if send_message(msg, chat_id=chat_id):
                logger.info("주간 성과 리포트 전송 완료")
            else:
                logger.error("주간 성과 리포트 전송 실패")
        else:
            logger.warning("AUTO_TRADE_CHAT_ID 미설정 — 리포트 미전송")

        return perf_7d

    def daily_summary(self) -> Optional[str]:
        """일일 거래 요약을 생성하고 전송한다."""
        today = date.today().isoformat()
        daily = self.state.get_daily_pnl(today)

        if not daily or daily["trades_count"] == 0:
            return None

        open_positions = self.tracker.get_all_open()

        msg_lines = [
            "<b>[자율매매] 일일 요약</b>",
            f"날짜: {today}",
            "",
            f"거래: {daily['trades_count']}건 "
            f"(승 {daily['wins']} / 패 {daily['losses']})",
            f"실현 PnL: {daily['realized_pnl']:+,}원",
            f"보유 종목: {len(open_positions)}개",
        ]

        if open_positions:
            msg_lines.append("")
            msg_lines.append("<b>보유 현황:</b>")
            for pos in open_positions:
                entry = pos["entry_price"]
                name = pos["name"]
                ticker = pos["ticker"]
                msg_lines.append(f"  {name}({ticker}) 진입가 {entry:,}원")

        msg = "\n".join(msg_lines)

        chat_id = AUTO_CONFIG.auto_trade_chat_id
        if chat_id:
            send_message(msg, chat_id=chat_id)

        return msg

    def send_trade_notification(
        self, side: str, name: str, ticker: str,
        quantity: int, price: int,
        reason: str = "", pnl_pct: float = None,
    ) -> None:
        """매매 체결 알림을 전송한다."""
        chat_id = AUTO_CONFIG.auto_trade_chat_id
        if not chat_id:
            return

        emoji = "🟢" if side == "buy" else "🔴"
        action = "매수" if side == "buy" else "매도"

        lines = [
            f"{emoji} <b>[자율매매] {action} 체결</b>",
            f"종목: {name} ({ticker})",
            f"수량: {quantity}주 @ {price:,}원",
            f"금액: {quantity * price:,}원",
        ]

        if reason:
            lines.append(f"사유: {reason}")

        if pnl_pct is not None:
            pnl_emoji = "📈" if pnl_pct > 0 else "📉"
            lines.append(f"{pnl_emoji} 수익률: {pnl_pct:+.1f}%")

        if AUTO_CONFIG.dry_run:
            lines.append("\n<i>(시뮬레이션 모드)</i>")

        send_message("\n".join(lines), chat_id=chat_id)

    def _format_weekly_report(
        self, perf_7d: Dict, perf_30d: Dict,
        weekly_pnl: Dict, open_positions: list,
        recent_trades: list,
    ) -> str:
        """주간 리포트 메시지를 포맷한다."""
        lines = [
            "<b>📊 [자율매매] 주간 성과 리포트</b>",
            f"기간: 최근 7일 | 날짜: {date.today().isoformat()}",
            "",
        ]

        # 주간 성과
        lines.append("<b>▸ 주간 성과</b>")
        lines.append(f"  거래: {perf_7d['total_trades']}건 "
                      f"(승 {perf_7d['wins']} / 패 {perf_7d['losses']})")
        lines.append(f"  승률: {perf_7d['win_rate']}%")
        lines.append(f"  누적 PnL: {perf_7d['total_pnl']:+,}원")
        lines.append(f"  평균 PnL: {perf_7d['avg_pnl_pct']:+.2f}%")
        if perf_7d['total_trades'] > 0:
            lines.append(f"  최고: {perf_7d['best_trade_pct']:+.2f}% "
                          f"/ 최저: {perf_7d['worst_trade_pct']:+.2f}%")
        lines.append("")

        # 30일 누적
        lines.append("<b>▸ 30일 누적</b>")
        lines.append(f"  거래: {perf_30d['total_trades']}건 "
                      f"| 승률: {perf_30d['win_rate']}%")
        lines.append(f"  누적 PnL: {perf_30d['total_pnl']:+,}원")
        lines.append(f"  최대 낙폭: {perf_30d['max_drawdown_pct']:.1f}%")
        lines.append(f"  연속 패배: {perf_30d['consecutive_losses']}연패")
        lines.append("")

        # 보유 현황
        lines.append(f"<b>▸ 보유 현황</b> ({len(open_positions)}종목)")
        if open_positions:
            for pos in open_positions[:10]:
                name = pos["name"]
                entry = pos["entry_price"]
                lines.append(f"  {name} | 진입 {entry:,}원")
        else:
            lines.append("  (보유 종목 없음)")
        lines.append("")

        # 최근 거래
        if recent_trades:
            lines.append(f"<b>▸ 최근 거래</b> ({len(recent_trades)}건)")
            for trade in recent_trades[:5]:
                side_kr = "매수" if trade["side"] == "buy" else "매도"
                pnl_str = ""
                if trade.get("pnl_pct") is not None:
                    pnl_str = f" ({trade['pnl_pct']:+.1f}%)"
                lines.append(
                    f"  {trade['trade_date']} {side_kr} "
                    f"{trade['name']} {trade['quantity']}주 "
                    f"@ {trade['price']:,}원{pnl_str}"
                )

        # 모드 표시
        lines.append("")
        mode = "시뮬레이션" if AUTO_CONFIG.dry_run else "실전"
        env = "모의투자" if AUTO_CONFIG.use_mock else "실전투자"
        lines.append(f"<i>모드: {mode} ({env})</i>")

        return "\n".join(lines)
