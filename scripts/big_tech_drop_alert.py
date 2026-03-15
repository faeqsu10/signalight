import sys
import os
import logging

# 프로젝트 루트 경로 추가 (모듈 import 용)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.us_fetcher import fetch_us_stock_data
from bot.telegram import send_message

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("big_tech_alert")

# 알림 대상 빅테크 종목 및 목표 분할 매수 하락율(%) 설정
TARGET_STOCKS = {
    "NVDA": "엔비디아",
    "PLTR": "팔란티어",
    "MSFT": "마이크로소프트",
    "GOOGL": "알파벳(구글)",
    "AMZN": "아마존",
    "META": "메타",
    "TSLA": "테슬라"
}

# 알림을 받을 고점 대비 하락 기준선 (%)
DROP_THRESHOLDS = [10, 15, 20, 25, 30, 35, 40, 50]

def check_drops_and_alert():
    logger.info("빅테크 가격 분할 매수 알림 스캔을 시작합니다...")
    messages = []
    
    for symbol, name in TARGET_STOCKS.items():
        # 52주(약 365일) 데이터 가져오기
        df = fetch_us_stock_data(symbol, days=365)
        if df is None or df.empty:
            logger.error(f"데이터를 가져오지 못했습니다: {symbol}")
            continue
            
        current_price = float(df['종가'].iloc[-1])
        high_idx = df['고가'].idxmax()
        high_52w = float(df['고가'].loc[high_idx])
        high_date = high_idx.strftime('%Y-%m-%d') if hasattr(high_idx, 'strftime') else str(high_idx).split(' ')[0]
        
        # 고점 대비 하락율 계산
        drop_pct = ((high_52w - current_price) / high_52w) * 100
        
        # 가장 근접하여 돌파한 하락 기준선 찾기
        crossed_threshold = None
        for threshold in reversed(DROP_THRESHOLDS):
            if drop_pct >= threshold:
                crossed_threshold = threshold
                break
                
        logger.info(f"{name}({symbol}): 현재가 ${current_price:.2f} (52주 최고 ${high_52w:.2f} at {high_date}) -> 하락율: -{drop_pct:.2f}%")
        
        if crossed_threshold:
            msg = (
                f"🚨 <b>{name} ({symbol}) 매수 타점 도달</b> 🚨\n"
                f"• 현재가: ${current_price:.2f}\n"
                f"• 52주 최고가: ${high_52w:.2f} ({high_date})\n"
                f"• <b>고점 대비 하락율: -{drop_pct:.2f}%</b> (기준: -{crossed_threshold}%)\n"
                f"👉 분할 매수를 고려해 볼 만한 구간입니다."
            )
            messages.append(msg)
            
    if messages:
        final_message = "<b>[빅테크 가격 분할 매수 모니터링]</b>\n\n" + "\n\n".join(messages)
        success = send_message(final_message)
        if success:
            logger.info("텔레그램 알림을 성공적으로 발송했습니다.")
        else:
            logger.error("텔레그램 알림 발송에 실패했습니다.")
    else:
        logger.info("현재 설정된 하락율 기준에 도달한 종목이 없습니다.")

if __name__ == "__main__":
    check_drops_and_alert()
