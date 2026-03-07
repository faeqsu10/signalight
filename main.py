import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict

from config import WATCH_LIST, DATA_PERIOD_DAYS
from data.fetcher import fetch_stock_data
from data.investor import fetch_investor_trading
from data.news import fetch_news
from signals.strategy import analyze_detailed
from signals.sentiment import analyze_sentiment
from bot.telegram import send_message
from bot.formatter import format_signal_alert, format_daily_briefing, format_weekly_report


def _collect_stock_data() -> List[Dict]:
    """모든 감시 종목의 구조화된 데이터를 수집한다."""
    stock_data_list = []

    for ticker, name in WATCH_LIST:
        try:
            df = fetch_stock_data(ticker)
            if df.empty:
                print(f"  {name}({ticker}): 데이터 없음")
                continue

            investor_df = None
            try:
                investor_df = fetch_investor_trading(ticker)
            except Exception as e:
                print(f"  {name}({ticker}) 외인/기관 데이터 조회 실패: {e}")

            data = analyze_detailed(df, ticker, name, investor_df=investor_df)

            # 뉴스 감성 분석 (실패해도 기존 알림에 영향 없음)
            try:
                headlines_data = fetch_news(ticker, limit=5)
                if headlines_data:
                    headlines = [h["title"] for h in headlines_data]
                    sentiment_result = analyze_sentiment(headlines, name)
                    data["news_sentiment"] = sentiment_result
                else:
                    data["news_sentiment"] = None
            except Exception as e:
                print(f"  {name}({ticker}) 뉴스 감성 분석 실패: {e}")
                data["news_sentiment"] = None

            stock_data_list.append(data)
        except Exception as e:
            print(f"  {name}({ticker}) 에러: {e}")

    return stock_data_list


def check_signals():
    """감시 종목들의 시그널을 확인하고 알림을 보낸다."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 시그널 체크 시작...")

    stock_data_list = _collect_stock_data()

    # 시그널 있는 종목만 필터
    signal_stocks = [s for s in stock_data_list if s.get("signals")]

    if signal_stocks:
        for s in signal_stocks:
            for sig in s["signals"]:
                print(f"  >> [{sig['trigger']}] {s['name']} - {sig['detail']}")

        message = format_signal_alert(stock_data_list)
        send_message(message)
        total = sum(len(s["signals"]) for s in signal_stocks)
        print(f"\n  총 {total}개 시그널 전송 완료!")
    else:
        print("\n  시그널 없음. 알림 미전송.")


def daily_briefing():
    """장마감 후 전 종목 일일 요약 브리핑을 전송한다."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 일일 브리핑 시작...")

    stock_data_list = _collect_stock_data()

    if stock_data_list:
        message = format_daily_briefing(stock_data_list)
        send_message(message)
        print(f"  일일 브리핑 전송 완료! ({len(stock_data_list)}개 종목)")
    else:
        print("  데이터 수집 실패. 브리핑 미전송.")


def weekly_report():
    """주간 리포트를 전송한다 (금요일 장마감 후)."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 주간 리포트 시작...")

    stock_data_list = []
    weekly_signals = []  # type: List[Dict]

    for ticker, name in WATCH_LIST:
        try:
            # 주간 데이터: 최근 10일 (약 2주 거래일)
            end_dt = datetime.today()
            start_dt = end_dt - timedelta(days=14)
            df = fetch_stock_data(
                ticker,
                start_date=start_dt.strftime("%Y%m%d"),
                end_date=end_dt.strftime("%Y%m%d"),
            )
            if df.empty or len(df) < 2:
                continue

            # 주간 등락률 계산 (이번 주 월요일 ~ 금요일)
            today = datetime.today()
            monday = today - timedelta(days=today.weekday())
            week_df = df[df.index >= monday.strftime("%Y-%m-%d")]

            if len(week_df) >= 2:
                week_open = float(week_df["종가"].iloc[0])
                week_close = float(week_df["종가"].iloc[-1])
                weekly_change = ((week_close - week_open) / week_open * 100) if week_open != 0 else 0.0
            elif len(week_df) == 1:
                weekly_change = 0.0
            else:
                weekly_change = 0.0

            investor_df = None
            try:
                investor_df = fetch_investor_trading(ticker)
            except Exception:
                pass

            data = analyze_detailed(df, ticker, name, investor_df=investor_df)
            data["weekly_change_pct"] = round(weekly_change, 2)
            stock_data_list.append(data)

            # 이번 주 시그널 수집
            for sig in data.get("signals", []):
                weekly_signals.append({
                    "name": name,
                    "ticker": ticker,
                    "date": today.strftime("%m/%d"),
                    "trigger": sig["trigger"],
                    "type": sig["type"],
                })
        except Exception as e:
            print(f"  {name}({ticker}) 에러: {e}")

    if stock_data_list:
        message = format_weekly_report(stock_data_list, weekly_signals)
        send_message(message)
        print(f"  주간 리포트 전송 완료! ({len(stock_data_list)}개 종목)")
    else:
        print("  데이터 수집 실패. 주간 리포트 미전송.")


def main():
    print("=== Signalight 시작 ===")
    print(f"감시 종목: {', '.join(name for _, name in WATCH_LIST)}")

    # 시작할 때 한 번 실행
    check_signals()

    # 평일 장중 30분마다 체크 (09:30 ~ 15:30)
    for hour in range(9, 16):
        for minute in (0, 30):
            if hour == 9 and minute == 0:
                continue
            if hour == 15 and minute > 30:
                continue
            t = f"{hour:02d}:{minute:02d}"
            for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
                getattr(schedule.every(), day).at(t).do(check_signals)

    # 평일 장마감 후 일일 브리핑 (16:00)
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        getattr(schedule.every(), day).at("16:00").do(daily_briefing)

    # 주간 리포트 (매주 금요일 16:30)
    schedule.every().friday.at("16:30").do(weekly_report)

    print("스케줄 등록 완료:")
    print("  - 평일 09:30~15:30 매 30분: 시그널 체크")
    print("  - 평일 16:00: 일일 브리핑")
    print("  - 금요일 16:30: 주간 리포트")
    print("실행 중... (Ctrl+C로 종료)\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
