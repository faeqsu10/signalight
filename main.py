import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict

from config import WATCH_LIST as _CONFIG_WATCH_LIST, DATA_PERIOD_DAYS
from data.fetcher import fetch_stock_data, fetch_vix
from data.investor import fetch_investor_trading
from data.news import fetch_news
from signals.sentiment import analyze_sentiment
from signals.strategy import analyze_detailed
from bot.telegram import send_message
from bot.formatter import format_signal_alert, format_daily_briefing, format_weekly_report
from signals.llm_analyzer import analyze_comprehensive, should_call_llm
from storage.db import init_db, save_signals, save_sentiment, save_llm_analysis, get_active_watchlist
from bot.interactive import InteractiveBot, set_emergency_stop_callback
from trading import TradingConfig
from trading.executor import TradeExecutor
from infra.logging_config import setup_logging

logger = setup_logging()

# DB 초기화
init_db()


def _get_watchlist():
    """DB 우선, config.py 폴백으로 감시 종목 리스트를 반환한다."""
    try:
        wl = get_active_watchlist()
        if wl:
            return wl
    except Exception as e:
        logger.warning("DB 워치리스트 조회 실패, config 폴백: %s", e)
    return _CONFIG_WATCH_LIST

# 자동매매 (dry_run=True 기본, 실제 주문 없이 시뮬레이션)
_trading_config = TradingConfig(dry_run=True, use_mock=True)
_executor = TradeExecutor(config=_trading_config)
_interactive_bot = InteractiveBot()


def _collect_stock_data() -> List[Dict]:
    """모든 감시 종목의 구조화된 데이터를 수집한다."""
    stock_data_list = []

    # VIX 1회 조회 후 전 종목에 전달 (중복 호출 방지)
    vix_value = None
    try:
        vix_series = fetch_vix()
        if not vix_series.empty:
            vix_value = float(vix_series.iloc[-1])
            logger.info("VIX 공포지수: %.1f", vix_value)
    except Exception as e:
        logger.warning("VIX 조회 실패: %s", e)

    watchlist = _get_watchlist()
    for ticker, name in watchlist:
        try:
            df = fetch_stock_data(ticker)
            if df.empty:
                logger.warning("%s(%s): 데이터 없음", name, ticker)
                continue

            investor_df = None
            try:
                investor_df = fetch_investor_trading(ticker)
            except Exception as e:
                logger.warning("%s(%s) 외인/기관 데이터 조회 실패: %s", name, ticker, e)

            data = analyze_detailed(df, ticker, name, investor_df=investor_df, vix_value=vix_value)

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
                logger.warning("%s(%s) 뉴스 감성 분석 실패: %s", name, ticker, e)
                data["news_sentiment"] = None

            # DB 저장 (시그널 + 감성)
            try:
                save_signals(data)
                save_sentiment(ticker, name, data.get("news_sentiment"))
            except Exception as e:
                logger.warning("%s(%s) DB 저장 실패: %s", name, ticker, e)

            # LLM 종합 판단 (상충 시그널 또는 합류 점수 >= 2)
            try:
                if should_call_llm(data):
                    llm_result = analyze_comprehensive(data)
                    if llm_result:
                        data["llm_analysis"] = llm_result
                        save_llm_analysis(ticker, name, llm_result, "gemini-2.5-flash")
                        logger.info("%s(%s) LLM 판단: %s (신뢰도 %.0f%%)",
                                    name, ticker, llm_result.get("verdict", ""),
                                    llm_result.get("confidence", 0) * 100)
            except Exception as e:
                logger.warning("%s(%s) LLM 분석 실패: %s", name, ticker, e)

            # 자동매매 시뮬레이션 (dry_run 모드)
            try:
                trade_data = {
                    "ticker": ticker,
                    "name": name,
                    "signal": data.get("confluence_direction", "hold"),
                    "confluence_score": data.get("confluence_score", 0),
                    "current_price": data.get("price", 0),
                }
                order = _executor.execute_signal(trade_data)
                if order:
                    data["trade_order"] = {
                        "side": order.side,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status,
                    }
            except Exception as e:
                logger.warning("%s(%s) 자동매매 시뮬레이션 실패: %s", name, ticker, e)

            stock_data_list.append(data)
        except Exception as e:
            logger.error("%s(%s) 에러: %s", name, ticker, e)

    return stock_data_list


def check_signals():
    """감시 종목들의 시그널을 확인하고 알림을 보낸다."""
    logger.info("시그널 체크 시작...")

    stock_data_list = _collect_stock_data()

    # 시그널 있는 종목만 필터
    signal_stocks = [s for s in stock_data_list if s.get("signals")]

    if signal_stocks:
        for s in signal_stocks:
            for sig in s["signals"]:
                logger.info("[%s] %s - %s", sig["trigger"], s["name"], sig["detail"])

        message = format_signal_alert(stock_data_list)
        if send_message(message):
            total = sum(len(s["signals"]) for s in signal_stocks)
            logger.info("총 %d개 시그널 전송 완료", total)
        else:
            logger.error("시그널 알림 텔레그램 전송 실패")
    else:
        logger.info("시그널 없음. 알림 미전송.")


def daily_briefing():
    """장마감 후 전 종목 일일 요약 브리핑을 전송한다."""
    logger.info("일일 브리핑 시작...")

    stock_data_list = _collect_stock_data()

    if stock_data_list:
        message = format_daily_briefing(stock_data_list)
        if send_message(message):
            logger.info("일일 브리핑 전송 완료 (%d개 종목)", len(stock_data_list))
        else:
            logger.error("일일 브리핑 텔레그램 전송 실패")
    else:
        logger.warning("데이터 수집 실패. 브리핑 미전송.")


def weekly_report():
    """주간 리포트를 전송한다 (금요일 장마감 후)."""
    logger.info("주간 리포트 시작...")

    stock_data_list = []
    weekly_signals = []  # type: List[Dict]

    # VIX 1회 조회
    vix_value = None
    try:
        vix_series = fetch_vix()
        if not vix_series.empty:
            vix_value = float(vix_series.iloc[-1])
    except Exception:
        pass

    watchlist = _get_watchlist()
    for ticker, name in watchlist:
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

            data = analyze_detailed(df, ticker, name, investor_df=investor_df, vix_value=vix_value)
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
            logger.error("%s(%s) 에러: %s", name, ticker, e)

    if stock_data_list:
        message = format_weekly_report(stock_data_list, weekly_signals)
        if send_message(message):
            logger.info("주간 리포트 전송 완료 (%d개 종목)", len(stock_data_list))
        else:
            logger.error("주간 리포트 텔레그램 전송 실패")
    else:
        logger.warning("데이터 수집 실패. 주간 리포트 미전송.")


def healthcheck():
    """매일 09:00 헬스체크 메시지를 전송한다."""
    msg = f"[헬스체크] Signalight 정상 동작 중 ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    try:
        send_message(msg)
        logger.info("헬스체크 전송 완료")
    except Exception as e:
        logger.error("헬스체크 전송 실패: %s", e)


def main():
    logger.info("=== Signalight 시작 ===")
    watchlist = _get_watchlist()
    logger.info("감시 종목: %s", ", ".join(name for _, name in watchlist))

    # 텔레그램 인터랙티브 봇 시작 (백그라운드 스레드)
    set_emergency_stop_callback(_executor.emergency_stop)
    _interactive_bot.start()
    logger.info("텔레그램 인터랙티브 봇 활성화 (/help, /stop, /status, /scan)")

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

    # 매일 09:00 헬스체크
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        getattr(schedule.every(), day).at("09:00").do(healthcheck)

    logger.info("스케줄 등록 완료:")
    logger.info("  - 평일 09:00: 헬스체크")
    logger.info("  - 평일 09:30~15:30 매 30분: 시그널 체크")
    logger.info("  - 평일 16:00: 일일 브리핑")
    logger.info("  - 금요일 16:30: 주간 리포트")
    logger.info("실행 중... (Ctrl+C로 종료)")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
