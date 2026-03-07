"""백테스트 CLI 러너.

커맨드라인에서 백테스트를 실행하고 결과를 출력한다.

Usage:
    python3 -m backtest.runner                    # config.py WATCH_LIST 전체
    python3 -m backtest.runner 005930 삼성전자     # 특정 종목
    python3 -m backtest.runner --days 365          # 기간 지정
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

from config import WATCH_LIST, DATA_PERIOD_DAYS
from data.fetcher import fetch_stock_data
from signals.strategy import generate_signals
from backtest.engine import BacktestEngine
from backtest.report import format_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="시그널 백테스트 러너")
    parser.add_argument("ticker", nargs="?", default=None, help="종목코드 (예: 005930)")
    parser.add_argument("name", nargs="?", default=None, help="종목명 (예: 삼성전자)")
    parser.add_argument("--days", type=int, default=DATA_PERIOD_DAYS, help="조회 기간 (일)")
    parser.add_argument("--capital", type=float, default=10_000_000, help="초기 자본금")
    parser.add_argument("--commission", type=float, default=0.00015, help="수수료율 (기본: 0.015%%)")
    parser.add_argument("--slippage", type=float, default=0.001, help="슬리피지율 (기본: 0.1%%)")
    return parser.parse_args()


def build_watchlist(args: argparse.Namespace) -> List[Tuple[str, str]]:
    if args.ticker and args.name:
        return [(args.ticker, args.name)]
    elif args.ticker:
        return [(args.ticker, args.ticker)]
    return WATCH_LIST


def main() -> None:
    args = parse_args()
    watchlist = build_watchlist(args)

    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=args.days)
    end_str = end_dt.strftime("%Y%m%d")
    start_str = start_dt.strftime("%Y%m%d")

    engine = BacktestEngine(
        initial_capital=args.capital,
        commission_rate=args.commission,
        slippage_rate=args.slippage,
    )

    for ticker, name in watchlist:
        print(f"\n{'='*60}")
        print(f" {name} ({ticker}) 백테스트 실행 중...")
        print(f" 기간: {start_str} ~ {end_str} ({args.days}일)")
        print(f"{'='*60}\n")

        df = fetch_stock_data(ticker, start_date=start_str, end_date=end_str)

        if df.empty:
            print(f"  [경고] {name}({ticker}) 데이터를 가져올 수 없습니다. 건너뜁니다.")
            continue

        signals = generate_signals(df, ticker, name)
        result = engine.run(df, signals, ticker=ticker, name=name)
        report = format_report(result)
        print(report)

    print(f"\n{'='*60}")
    print(" 백테스트 완료")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
