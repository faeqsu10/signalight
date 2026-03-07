"""백테스트 결과 리포트 생성기"""
from typing import Optional
from backtest import BacktestResult, Trade


def format_report(result: BacktestResult) -> str:
    """텍스트 형식 백테스트 리포트 생성"""
    lines = []

    # 헤더
    lines.append("=" * 60)
    lines.append(f"  백테스트 리포트: {result.name} ({result.ticker})")
    lines.append(f"  기간: {result.start_date} ~ {result.end_date}")
    lines.append("=" * 60)

    # 요약
    lines.append("")
    lines.append("[요약]")
    lines.append(f"  초기 자본    : {result.initial_capital:>15,.0f} 원")
    lines.append(f"  최종 자본    : {result.final_capital:>15,.0f} 원")
    pnl_sign = "+" if result.total_return_pct >= 0 else ""
    lines.append(f"  총 수익률    : {pnl_sign}{result.total_return_pct:>14.2f} %")
    lines.append(f"  최대 낙폭    : -{result.max_drawdown_pct:>14.2f} %")
    lines.append(f"  총 거래 횟수 : {result.total_trades:>15} 회")
    lines.append(f"  승리 / 패배  : {result.winning_trades} / {result.losing_trades}")
    lines.append(f"  승률         : {result.win_rate:>14.1f} %")
    avg_sign = "+" if result.avg_return_per_trade >= 0 else ""
    lines.append(f"  평균 거래 수익: {avg_sign}{result.avg_return_per_trade:>13.2f} %")

    # 경고
    warnings = []
    if result.max_drawdown_pct > 20.0:
        warnings.append(f"  [경고] 최대 낙폭이 {result.max_drawdown_pct:.1f}%로 20%를 초과합니다. 리스크가 높습니다.")
    if result.total_trades < 10:
        warnings.append(f"  [경고] 거래 횟수({result.total_trades}회)가 10회 미만입니다. 통계적 신뢰도가 낮을 수 있습니다.")

    if warnings:
        lines.append("")
        lines.append("[경고]")
        for w in warnings:
            lines.append(w)

    # 거래 내역
    if result.trades:
        lines.append("")
        lines.append("[거래 내역]")
        header = f"  {'매수일':<12} {'매수가':>10} {'매도일':<12} {'매도가':>10} {'수익률':>8}"
        lines.append(header)
        lines.append("  " + "-" * 56)
        for trade in result.trades:
            exit_date_str = str(trade.exit_date) if trade.exit_date else "미청산"
            exit_price_str = f"{trade.exit_price:>10,.0f}" if trade.exit_price is not None else f"{'N/A':>10}"
            ret_sign = "+" if trade.return_pct >= 0 else ""
            ret_str = f"{ret_sign}{trade.return_pct:.2f}%"
            lines.append(
                f"  {str(trade.entry_date):<12} {trade.entry_price:>10,.0f} "
                f"{exit_date_str:<12} {exit_price_str} {ret_str:>8}"
            )

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def format_telegram_message(result: BacktestResult) -> str:
    """텔레그램용 간결한 백테스트 결과 메시지"""
    ret_sign = "+" if result.total_return_pct >= 0 else ""
    ret_emoji = "📈" if result.total_return_pct >= 0 else "📉"

    lines = [
        f"📊 백테스트 결과: {result.name} ({result.ticker})",
        f"기간: {result.start_date} ~ {result.end_date}",
        "",
        f"{ret_emoji} 총 수익률: {ret_sign}{result.total_return_pct:.2f}%",
        f"📉 최대 낙폭: -{result.max_drawdown_pct:.2f}%",
        f"🎯 승률: {result.win_rate:.1f}% ({result.winning_trades}W/{result.losing_trades}L)",
        f"🔢 거래 횟수: {result.total_trades}회",
    ]

    return "\n".join(lines)
