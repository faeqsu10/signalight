"""성과 평가기 — 주간 리포트 + 텔레그램 전송.

PositionTracker와 PipelineState의 데이터를 기반으로
승률, 평균 PnL, 최대 낙폭 등을 계산하고 텔레그램으로 전송한다.
"""

import logging
from datetime import date
from typing import Dict, Optional, List

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
        currency: str = "원",
    ):
        self.state = state or PipelineState()
        self.tracker = position_tracker or PositionTracker()
        self._currency = currency

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

    def daily_summary(self, optimizer_status: Optional[Dict] = None) -> Optional[str]:
        """일일 거래 요약을 생성하고 전송한다.

        거래 유무와 관계없이 항상 파이프라인 실행 결과를 전송한다.
        """
        today = date.today().isoformat()
        daily = self.state.get_daily_pnl(today)
        open_positions = self.tracker.get_all_open()

        trades_count = daily["trades_count"] if daily else 0
        wins = daily["wins"] if daily else 0
        losses = daily["losses"] if daily else 0
        realized_pnl = daily["realized_pnl"] if daily else 0

        mode = "시뮬레이션" if AUTO_CONFIG.dry_run else "실전"

        msg_lines = [
            f"<b>[자율매매] 일일 요약 ({mode})</b>",
            f"날짜: {today}",
            "",
        ]

        if trades_count > 0:
            msg_lines.append(
                f"거래: {trades_count}건 "
                f"(승 {wins} / 패 {losses})"
            )
            msg_lines.append(f"실현 PnL: {realized_pnl:+,}{self._currency}")
        else:
            msg_lines.append("거래: 0건 (시그널 충족 종목 없음)")

        msg_lines.append(f"보유 종목: {len(open_positions)}개")

        if open_positions:
            msg_lines.append("")
            msg_lines.append("<b>보유 현황:</b>")
            for pos in open_positions:
                entry = pos["entry_price"]
                name = pos["name"]
                ticker = pos["ticker"]
                msg_lines.append(f"  {name}({ticker}) 진입가 {self._fmt_price(entry)}")

        if optimizer_status:
            msg_lines.append("")
            msg_lines.extend(self._format_optimizer_status(optimizer_status))

        msg = "\n".join(msg_lines)

        chat_id = AUTO_CONFIG.auto_trade_chat_id
        if chat_id:
            send_message(msg, chat_id=chat_id)

        return msg

    def _fmt_price(self, value, sign: bool = False) -> str:
        """통화에 맞게 가격을 포맷한다. KR: 1,000원 / US: $1,000"""
        if self._currency == "$":
            fmt = f"{value:+,.2f}" if sign else f"{value:,.2f}"
            return f"${fmt}"
        else:
            fmt = f"{value:+,}" if sign else f"{value:,}"
            return f"{fmt}{self._currency}"

    def _format_optimizer_status(self, status: Dict) -> List[str]:
        """피드백 루프(optimizer) 상태를 초보자 친화적으로 포맷한다."""
        lines = ["<b>피드백 루프 상태</b>"]

        active = bool(status.get("active", False))
        total = int(status.get("total_trades", 0) or 0)
        min_trades = int(status.get("min_trades", 20) or 20)
        win_rate = float(status.get("overall_win_rate", 0.0) or 0.0)

        if active:
            lines.append(
                f"적용: ON (샘플 {total}건, 승률 {win_rate:.1f}%)"
            )
        else:
            if total < min_trades:
                lines.append(f"적용: OFF (샘플 부족 {total}/{min_trades}건)")
            else:
                lines.append(f"적용: OFF (WF 기준 미충족, 샘플 {total}건)")
            lines.append("현재는 기본 기준으로 매매합니다.")

        reason = status.get("adjustment_reason", "")
        if reason:
            lines.append(f"판단 사유: {reason}")

        wf_valid = int(status.get("wf_valid_folds", 0) or 0)
        if wf_valid > 0:
            wf_passes = int(status.get("wf_passes", 0) or 0)
            wf_required = int(status.get("wf_required_passes", 0) or 0)
            avg_imp = float(status.get("avg_improvement", 0.0) or 0.0)
            imp_th = float(status.get("improvement_threshold", 0.0) or 0.0)
            lines.append(
                f"WF 비교: {wf_passes}/{wf_valid} 통과 (기준 {wf_required}), "
                f"평균 개선 {avg_imp:+.3f} / 기준 +{imp_th:.2f}"
            )

        latest = status.get("latest_change")
        if latest:
            lines.append(
                f"최근 이력: {latest.get('evaluated_at', '')} | "
                f"{'적용' if int(latest.get('applied', 0) or 0) == 1 else '미적용'}"
            )

        default_w = status.get("default_scan_weights", {})
        scan_w = status.get("scan_weights", {})
        default_t = status.get("default_buy_thresholds", {})
        buy_t = status.get("buy_thresholds", {})

        scan_lines = self._format_changes(
            title="스캔 가중치 변화",
            mapping_order=[
                ("golden_cross", "골든크로스"),
                ("rsi_oversold", "RSI 과매도"),
                ("volume_surge", "거래량 급증"),
            ],
            before=default_w,
            after=scan_w,
        )
        threshold_lines = self._format_changes(
            title="진입 임계값 변화",
            mapping_order=[
                ("uptrend", "상승장"),
                ("sideways", "횡보장"),
                ("downtrend", "하락장"),
            ],
            before=default_t,
            after=buy_t,
        )

        lines.extend(scan_lines)
        lines.extend(threshold_lines)

        lines.append("")
        lines.append("<b>초보자 설명</b>")
        lines.append(
            "스캔 가중치는 후보 선별 점수 비중입니다. 높을수록 그 신호를 더 중요하게 봅니다."
        )
        lines.append(
            "진입 임계값은 매수에 필요한 최소 점수입니다. 낮아지면 진입이 쉬워지고, 높아지면 보수적으로 진입합니다."
        )

        return lines

    def _format_changes(
        self,
        title: str,
        mapping_order: List[tuple],
        before: Dict,
        after: Dict,
    ) -> List[str]:
        lines = [f"<b>{title}</b>"]
        any_change = False

        for key, label in mapping_order:
            b = before.get(key)
            a = after.get(key)
            if b is None or a is None:
                continue

            delta = round(float(a) - float(b), 2)
            if delta == 0:
                sign = "유지"
            elif delta > 0:
                sign = f"상향 +{delta:.2f}"
                any_change = True
            else:
                sign = f"하향 {delta:.2f}"
                any_change = True

            lines.append(f"- {label}: {float(b):.2f} → {float(a):.2f} ({sign})")

        if not any_change:
            lines.append("- 변경 없음 (기본값 유지)")

        return lines

    def send_cycle_summary(
        self,
        flag: str,
        scan_count: int,
        analyze_count: int,
        buy_count: int,
        sell_count: int,
        top_candidates: List[Dict],
        currency: str = "KRW",
    ) -> None:
        """사이클 스캔 결과 요약을 텔레그램으로 전송한다.

        Args:
            flag: 국기 이모지 prefix (예: "🇰🇷" 또는 "🇺🇸")
            scan_count: 스캔으로 선정된 후보 종목 수
            analyze_count: 분석 완료 종목 수
            buy_count: 매수 체결 건수
            sell_count: 매도 체결 건수
            top_candidates: 상위 후보 리스트 (analyze_candidates 결과)
            currency: "KRW" 또는 "USD"
        """
        chat_id = AUTO_CONFIG.auto_trade_chat_id
        if not chat_id:
            return

        open_positions = self.tracker.get_all_open()
        equity_rows = self.state.get_equity_history(days=1)
        total_equity = 0
        mdd_pct = 0.0

        if equity_rows:
            latest = equity_rows[-1]
            total_equity = latest.get("total_equity", 0)

        perf = self.state.get_performance_summary(days=30)
        mdd_pct = perf.get("max_drawdown_pct", 0.0) or 0.0

        if currency == "USD":
            # equity는 cents 단위로 저장됨
            equity_display = f"${total_equity / 100:,.0f}" if total_equity else "$0"
            label = "US 자율매매"
        else:
            equity_display = f"₩{total_equity:,}" if total_equity else "₩0"
            label = "자율매매"

        lines = [
            f"{flag} <b>[{label}] 일일 스캔 리포트</b>",
            "━━━━━━━━━━━━━━━━━━",
            f"📊 스캔: {scan_count}종목 후보",
            f"📈 분석: {analyze_count}종목 완료",
            f"🎯 매수: {buy_count}건, 매도: {sell_count}건",
        ]

        # 상위 후보 (최대 5개)
        top = sorted(
            top_candidates,
            key=lambda x: x.get("confluence_score", 0),
            reverse=True,
        )[:5]

        if top:
            lines.append("")
            lines.append("상위 후보:")
            for item in top:
                name = item.get("name", item.get("ticker", ""))
                score = item.get("confluence_score", 0)
                signals = item.get("scan_signals", [])
                sig_str = "+".join(
                    self._scan_signal_short(s) for s in signals
                ) if signals else "-"
                lines.append(f"• {name} score={score:.1f} [{sig_str}]")

        # 포트폴리오 현황
        lines.append("")
        lines.append("포트폴리오:")
        lines.append(f"• 총 자산: {equity_display}")
        lines.append(f"• 보유: {len(open_positions)}종목")
        lines.append(f"• MDD: {mdd_pct:.1f}%")

        if AUTO_CONFIG.dry_run:
            lines.append("")
            lines.append("<i>(시뮬레이션 모드)</i>")

        send_message("\n".join(lines), chat_id=chat_id)

    def _scan_signal_short(self, signal: str) -> str:
        """스캔 시그널 코드를 짧은 한글 라벨로 변환한다."""
        mapping = {
            "golden_cross": "골든크로스",
            "rsi_oversold": "RSI",
            "volume_surge": "거래량",
            "near_golden_cross": "근접GC",
        }
        return mapping.get(signal, signal)

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
            f"수량: {quantity}주 @ {self._fmt_price(price)}",
            f"금액: {self._fmt_price(quantity * price)}",
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
        lines.append(f"  누적 PnL: {self._fmt_price(perf_7d['total_pnl'], sign=True)}")
        lines.append(f"  평균 PnL: {perf_7d['avg_pnl_pct']:+.2f}%")
        if perf_7d['total_trades'] > 0:
            lines.append(f"  최고: {perf_7d['best_trade_pct']:+.2f}% "
                          f"/ 최저: {perf_7d['worst_trade_pct']:+.2f}%")
        lines.append("")

        # 30일 누적
        lines.append("<b>▸ 30일 누적</b>")
        lines.append(f"  거래: {perf_30d['total_trades']}건 "
                      f"| 승률: {perf_30d['win_rate']}%")
        lines.append(f"  누적 PnL: {self._fmt_price(perf_30d['total_pnl'], sign=True)}")
        lines.append(f"  최대 낙폭: {perf_30d['max_drawdown_pct']:.1f}%")
        lines.append(f"  연속 패배: {perf_30d['consecutive_losses']}연패")
        lines.append("")

        # 보유 현황
        lines.append(f"<b>▸ 보유 현황</b> ({len(open_positions)}종목)")
        if open_positions:
            for pos in open_positions[:10]:
                name = pos["name"]
                entry = pos["entry_price"]
                lines.append(f"  {name} | 진입 {self._fmt_price(entry)}")
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
