import sys
import os
import logging
import json
import urllib.request
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.telegram import send_message

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("realtime_alert")

TARGET_STOCKS = {
    "NVDA": "엔비디아",
    "PLTR": "팔란티어",
    "MSFT": "마이크로소프트",
    "GOOGL": "알파벳(구글)",
    "AMZN": "아마존",
    "META": "메타",
    "TSLA": "테슬라"
}

DROP_THRESHOLDS = [10, 15, 20, 25, 30, 35, 40, 50]

# 알림 상태를 저장하여 중복 알림 방지
STATE_FILE = os.path.join(os.path.dirname(__file__), 'alert_state.json')

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"상태 파일 로드 실패: {e}")
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"상태 파일 저장 실패: {e}")

def get_realtime_data(symbol):
    """Yahoo Finance API를 사용해 실시간 가격(1분 단위)을 가져옵니다."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            return meta.get("regularMarketPrice")
    except Exception as e:
        logger.error(f"실시간 데이터 수집 실패 ({symbol}): {e}")
        return None
        
def get_daily_high(symbol):
    """최근 1년 치 일봉 데이터를 바탕으로 52주 최고가와 그 날짜를 구합니다."""
    try:
        now_ts = int(datetime.now().timestamp())
        period1 = int(now_ts - (365 * 24 * 3600))
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={period1}&period2={now_ts}&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            
            timestamps = data["chart"]["result"][0]["timestamp"]
            indicators = data["chart"]["result"][0]["indicators"]["quote"][0]
            highs = indicators["high"]
            
            valid_data = [(ts, h) for ts, h in zip(timestamps, highs) if h is not None]
            if valid_data:
                max_item = max(valid_data, key=lambda x: x[1])
                high_val = max_item[1]
                high_date = datetime.fromtimestamp(max_item[0]).strftime("%Y-%m-%d")
                return high_val, high_date
            return None, None
    except Exception as e:
        logger.error(f"52주 최고가 수집 실패 ({symbol}): {e}")
        return None, None

def check_realtime_drops():
    logger.info("실시간 장중 가격 모니터링을 시작합니다...")
    state = load_state()
    messages = []
    
    for symbol, name in TARGET_STOCKS.items():
        high_52w, high_date = get_daily_high(symbol)
        if not high_52w:
            continue
            
        current_price = get_realtime_data(symbol)
        if not current_price:
            continue
            
        drop_pct = ((high_52w - current_price) / high_52w) * 100
        
        # 현재 하락률이 돌파한 가장 큰 기준선 찾기
        crossed_threshold = None
        for threshold in reversed(DROP_THRESHOLDS):
            if drop_pct >= threshold:
                crossed_threshold = threshold
                break
                
        if crossed_threshold:
            # 이전에 알림을 보냈던 기준선 확인 (중복 알림 방지)
            prev_threshold = state.get(symbol, {}).get('last_alert_threshold', 0)
            
            # 더 깊은 기준선을 뚫었을 때만 알림 전송 (예: -20%에서 알림 받았는데, 장중에 폭락해서 -25% 돌파 시 추가 알림)
            if crossed_threshold > prev_threshold:
                logger.info(f"[{symbol}] 실시간 타점 도달: -{drop_pct:.2f}% (기준 -{crossed_threshold}%)")
                
                # 분할 매수 전략 가이드 추가
                strategy_msg = ""
                if drop_pct >= 30:
                    strategy_msg = "🔥 <b>강력 매수 구간</b> (대기 자금의 40% 이상 투입 고려)"
                elif drop_pct >= 20:
                    strategy_msg = "🎯 <b>적극 매수 구간</b> (대기 자금의 20~30% 투입 고려)"
                elif drop_pct >= 10:
                    strategy_msg = "👀 <b>관망 또는 소액 매수</b> (대기 자금의 10~15% 투입 고려)"

                # 종목별 우선순위 코멘트 (사용자 선호도 기반)
                if symbol == "NVDA":
                    strategy_msg += "\n💡 <b>우선순위 1순위</b> (엔비디아: 포트폴리오 핵심 비중 40% 목표)"
                elif symbol == "TSLA":
                    strategy_msg += "\n💡 <b>우선순위 2순위</b> (테슬라: 변동성 활용 비중 30% 목표)"
                elif symbol == "PLTR":
                    strategy_msg += "\n💡 <b>우선순위 3순위</b> (팔란티어: AI 성장성 포커스 비중 20% 목표)"
                elif symbol == "GOOGL":
                    strategy_msg += "\n💡 <b>보조 종목</b> (구글: 밸류에이션 매력 비중 10% 목표)"

                msg = (
                    f"⚡ <b>[실시간 장중 알림] {name} ({symbol}) 급락</b> ⚡\n"
                    f"• 현재가: ${current_price:.2f}\n"
                    f"• 52주 최고가: ${high_52w:.2f} ({high_date})\n"
                    f"• <b>현재 하락율: -{drop_pct:.2f}%</b> (기준: -{crossed_threshold}% 돌파)\n"
                    f"────────────────────\n"
                    f"📊 <b>액션 플랜 (매수 가이드)</b>\n"
                    f"{strategy_msg}"
                )
                messages.append(msg)
                
                state[symbol] = {
                    'last_alert_threshold': crossed_threshold,
                    'timestamp': datetime.now().isoformat()
                }
            # 주가가 다시 올라가서 기준선에서 멀어지면(예: 반등해서 -15%가 됨) 상태를 낮춰줌. 
            # 그래야 나중에 다시 떨어졌을 때 알림을 받을 수 있음.
            elif crossed_threshold < prev_threshold - 5: 
                state[symbol] = {
                    'last_alert_threshold': crossed_threshold,
                    'timestamp': datetime.now().isoformat()
                }
                
    if messages:
        final_message = "\n\n".join(messages)
        success = send_message(final_message)
        if success:
            logger.info("실시간 텔레그램 알림 발송 성공.")
            save_state(state) # 알림 성공 시에만 상태 저장
    else:
        logger.info("새로 돌파한 하락 기준선이 없습니다.")

if __name__ == "__main__":
    check_realtime_drops()
