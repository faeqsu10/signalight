import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.us_fetcher import fetch_us_stock_data

TARGET_STOCKS = {
    "NVDA": "엔비디아",
    "PLTR": "팔란티어",
    "MSFT": "마이크로소프트",
    "GOOGL": "구글",
    "AMZN": "아마존",
    "META": "메타",
    "TSLA": "테슬라"
}

def get_data():
    results = []
    
    for symbol, name in TARGET_STOCKS.items():
        try:
            df = fetch_us_stock_data(symbol, days=365)
            if df is None or df.empty:
                continue
                
            current_price = float(df['종가'].iloc[-1])
            high_idx = df['고가'].idxmax()
            high_52w = float(df['고가'].loc[high_idx])
            high_date = high_idx.strftime('%Y-%m-%d') if hasattr(high_idx, 'strftime') else str(high_idx).split(' ')[0]
            
            drop_pct = ((high_52w - current_price) / high_52w) * 100
            
            results.append({
                "symbol": symbol,
                "name": name,
                "currentPrice": round(current_price, 2),
                "high52w": round(high_52w, 2),
                "highDate": high_date,
                "dropPct": round(drop_pct, 2)
            })
        except Exception as e:
            continue
            
    # 하락률이 큰 순서대로 정렬
    results.sort(key=lambda x: x['dropPct'], reverse=True)
    print(json.dumps(results))

if __name__ == "__main__":
    get_data()