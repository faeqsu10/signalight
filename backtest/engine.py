"""백테스트 실행 엔진.

시그널 리스트와 OHLCV 데이터를 받아 매수/매도를 시뮬레이션하고
BacktestResult를 반환한다.
"""
import warnings
from typing import List, Optional

import pandas as pd

from backtest import BacktestResult, Signal, SignalType, Trade


class BacktestEngine:
    """시그널 기반 백테스트 엔진.

    - BUY 시그널 → 다음 거래일 시가로 매수
    - SELL 시그널 → 다음 거래일 시가로 매도
    - 수수료 0.015%, 슬리피지 0.1% 반영
    - 포지션 보유 중 BUY 시그널 무시, 미보유 시 SELL 시그널 무시
    """

    def __init__(
        self,
        initial_capital: float = 10_000_000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

    def run(
        self,
        df: pd.DataFrame,
        signals: List[Signal],
        ticker: str = "",
        name: str = "",
    ) -> BacktestResult:
        """백테스트를 실행하고 결과를 반환한다.

        Args:
            df: OHLCV DataFrame (인덱스: 날짜, 컬럼: 시가/고가/저가/종가/거래량)
            signals: generate_signals()가 생성한 시그널 리스트
            ticker: 종목코드
            name: 종목명
        """
        if ticker == "" and signals:
            ticker = signals[0].ticker
        if name == "" and signals:
            name = signals[0].name

        # 날짜 → 시그널 매핑 (같은 날 여러 시그널이면 strength가 높은 것 우선)
        signal_map = self._build_signal_map(signals)

        # 거래일 목록
        trading_dates = list(df.index)

        cash = self.initial_capital
        shares = 0
        position: Optional[Trade] = None
        trades: List[Trade] = []
        equity_curve: List[float] = []

        for i, current_date in enumerate(trading_dates):
            date_key = current_date.date() if hasattr(current_date, 'date') else current_date
            current_close = float(df.loc[current_date, "종가"])

            # 이전 거래일에 시그널이 있었으면 오늘 시가에 체결
            if i > 0:
                prev_date = trading_dates[i - 1]
                prev_date_key = prev_date.date() if hasattr(prev_date, 'date') else prev_date

                if prev_date_key in signal_map:
                    sig = signal_map[prev_date_key]
                    open_price = float(df.loc[current_date, "시가"])

                    if sig.signal_type == SignalType.BUY and shares == 0:
                        # 매수: 슬리피지 적용 (불리하게 높은 가격)
                        exec_price = open_price * (1 + self.slippage_rate)
                        commission = exec_price * self.commission_rate
                        cost_per_share = exec_price + commission
                        shares = int(cash / cost_per_share)

                        if shares > 0:
                            total_cost = shares * cost_per_share
                            cash -= total_cost
                            position = Trade(
                                ticker=ticker,
                                name=name,
                                entry_date=date_key,
                                entry_price=exec_price,
                                entry_signal=sig.source,
                                shares=shares,
                            )

                    elif sig.signal_type == SignalType.SELL and shares > 0 and position is not None:
                        # 매도: 슬리피지 적용 (불리하게 낮은 가격)
                        exec_price = open_price * (1 - self.slippage_rate)
                        commission = exec_price * self.commission_rate
                        proceeds_per_share = exec_price - commission
                        total_proceeds = shares * proceeds_per_share

                        cash += total_proceeds

                        # Trade 완성
                        position.exit_date = date_key
                        position.exit_price = exec_price
                        position.exit_signal = sig.source
                        pnl = total_proceeds - (shares * position.entry_price * (1 + self.commission_rate))
                        position.pnl = pnl
                        position.return_pct = (exec_price / position.entry_price - 1) * 100

                        trades.append(position)
                        shares = 0
                        position = None

            # equity = 현금 + 보유주식 평가액
            equity = cash + shares * current_close
            equity_curve.append(equity)

        # 마지막 날 미체결 포지션 강제 청산 (종가 기준)
        if shares > 0 and position is not None:
            last_close = float(df.iloc[-1]["종가"])
            exec_price = last_close * (1 - self.slippage_rate)
            commission = exec_price * self.commission_rate
            proceeds_per_share = exec_price - commission
            total_proceeds = shares * proceeds_per_share
            cash += total_proceeds

            last_date = trading_dates[-1]
            position.exit_date = last_date.date() if hasattr(last_date, 'date') else last_date
            position.exit_price = exec_price
            position.exit_signal = "FORCED_CLOSE"
            pnl = total_proceeds - (shares * position.entry_price * (1 + self.commission_rate))
            position.pnl = pnl
            position.return_pct = (exec_price / position.entry_price - 1) * 100

            trades.append(position)

            # equity_curve 마지막 값 갱신
            if equity_curve:
                equity_curve[-1] = cash

        # 결과 계산
        final_capital = cash
        total_return_pct = (final_capital / self.initial_capital - 1) * 100
        max_drawdown_pct = self._calc_max_drawdown(equity_curve)

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        total_trades = len(trades)
        win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0.0
        avg_return = sum(t.return_pct for t in trades) / total_trades if total_trades > 0 else 0.0

        if total_trades < 10:
            warnings.warn(
                f"거래 횟수가 {total_trades}회로 적습니다. "
                "통계적 신뢰도가 낮을 수 있습니다.",
                stacklevel=2,
            )

        start_date = trading_dates[0]
        end_date = trading_dates[-1]
        start_date = start_date.date() if hasattr(start_date, 'date') else start_date
        end_date = end_date.date() if hasattr(end_date, 'date') else end_date

        return BacktestResult(
            ticker=ticker,
            name=name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            avg_return_per_trade=avg_return,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _build_signal_map(self, signals: List[Signal]) -> dict:
        """날짜별 가장 강한 시그널 하나를 선택하여 매핑."""
        signal_map = {}  # type: dict
        for sig in signals:
            existing = signal_map.get(sig.date)
            if existing is None or sig.strength > existing.strength:
                signal_map[sig.date] = sig
        return signal_map

    @staticmethod
    def _calc_max_drawdown(equity_curve: List[float]) -> float:
        """equity curve에서 최대 낙폭(MDD)을 % 단위로 계산."""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd
