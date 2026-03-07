import schedule
import time
from datetime import datetime

from config import WATCH_LIST
from data.fetcher import fetch_stock_data
from signals.strategy import analyze
from bot.telegram import send_message


def check_signals():
    """감시 종목들의 시그널을 확인하고 알림을 보낸다."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 시그널 체크 시작...")

    all_signals = []

    for ticker, name in WATCH_LIST:
        try:
            df = fetch_stock_data(ticker)
            if df.empty:
                print(f"  {name}({ticker}): 데이터 없음")
                continue

            signals = analyze(df, name)
            if signals:
                all_signals.extend(signals)
                for s in signals:
                    print(f"  >> {s}")
            else:
                print(f"  {name}({ticker}): 시그널 없음")
        except Exception as e:
            print(f"  {name}({ticker}) 에러: {e}")

    if all_signals:
        header = f"📊 <b>Signalight 매매 시그널</b>\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        body = "\n".join(f"• {s}" for s in all_signals)
        send_message(header + "\n" + body)
        print(f"\n  총 {len(all_signals)}개 시그널 전송 완료!")
    else:
        print("\n  시그널 없음. 알림 미전송.")


def main():
    print("=== Signalight 시작 ===")
    print(f"감시 종목: {', '.join(name for _, name in WATCH_LIST)}")

    # 시작할 때 한 번 실행
    check_signals()

    # 평일 장 마감 후 매일 체크 (16:00)
    schedule.every().monday.at("16:00").do(check_signals)
    schedule.every().tuesday.at("16:00").do(check_signals)
    schedule.every().wednesday.at("16:00").do(check_signals)
    schedule.every().thursday.at("16:00").do(check_signals)
    schedule.every().friday.at("16:00").do(check_signals)

    print("스케줄 등록 완료 (평일 16:00)")
    print("실행 중... (Ctrl+C로 종료)\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
