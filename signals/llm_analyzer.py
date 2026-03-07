"""LLM 종합 판단 모듈 — Google Gemini로 상충 시그널 해석."""
import json
import requests
import logging
from typing import Dict, Optional

from config import GOOGLE_API_KEY, SENTIMENT_MODEL, SENTIMENT_TIMEOUT

logger = logging.getLogger("signalight")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 퀀트 애널리스트입니다.
주어진 기술적 지표, 수급 데이터, 뉴스 감성 분석 결과를 종합하여 매매 판단을 내려주세요.

반드시 아래 JSON 형식으로만 응답하세요:
{
  "verdict": "매수" | "매도" | "관망",
  "confidence": 0.0~1.0,
  "reasoning": "판단 근거를 2-3문장으로 요약",
  "risk_factors": ["위험 요소 1", "위험 요소 2"]
}"""


def analyze_comprehensive(stock_data: Dict) -> Optional[Dict]:
    """시그널 데이터를 종합하여 LLM에게 판단을 요청한다.

    호출 조건: 상충 시그널이 있거나 confluence_score >= 2일 때만 호출.
    실패 시 None 반환 (기존 기능에 영향 없음).
    """
    if not GOOGLE_API_KEY:
        return None

    # 입력 데이터 구성
    signals = stock_data.get("signals", [])
    indicators = stock_data.get("indicators", {})
    investor = stock_data.get("investor", {})
    sentiment = stock_data.get("news_sentiment")

    input_data = {
        "종목": stock_data.get("name", ""),
        "현재가": stock_data.get("price", 0),
        "등락률": stock_data.get("change_pct", 0),
        "시그널": [{"방향": s["type"], "트리거": s["trigger"], "설명": s["detail"]} for s in signals],
        "지표": {
            "RSI": indicators.get("rsi"),
            "MACD_히스토그램": indicators.get("macd_histogram"),
            "거래량_비율": indicators.get("volume_ratio"),
            "ATR": indicators.get("atr"),
            "ATR_손절가": indicators.get("atr_stop_loss"),
        },
        "수급": investor if investor else "데이터 없음",
        "뉴스_감성": {
            "판정": sentiment.get("sentiment", ""),
            "신뢰도": sentiment.get("confidence", 0),
            "요약": sentiment.get("summary", ""),
        } if sentiment else "데이터 없음",
        "합류_점수": stock_data.get("confluence_score", 0),
        "합류_방향": stock_data.get("confluence_direction", ""),
    }

    prompt = f"{SYSTEM_PROMPT}\n\n분석 데이터:\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"

    try:
        url = GEMINI_URL.format(SENTIMENT_MODEL)
        resp = requests.post(
            url,
            params={"key": GOOGLE_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 2048,
                },
            },
            timeout=SENTIMENT_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.warning("LLM 분석 API 오류: %d %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        # Gemini 2.5 Flash thinking 모델: thought=True 파트 건너뛰기
        parts = data["candidates"][0]["content"]["parts"]
        text = ""
        for part in parts:
            if part.get("thought"):
                continue
            text = part.get("text", "").strip()
            if text:
                break
        if not text:
            text = parts[-1].get("text", "").strip()

        # JSON 추출 (마크다운 코드블록 제거)
        lines = text.split("\n")
        cleaned = "\n".join(line for line in lines if not line.strip().startswith("```"))
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("LLM 분석: JSON 파싱 실패")
            return None

        result = json.loads(cleaned[start:end])
        result["input_data"] = input_data
        return result

    except requests.Timeout:
        logger.warning("LLM 분석 타임아웃")
        return None
    except Exception as e:
        logger.warning("LLM 분석 실패: %s", e)
        return None


def should_call_llm(stock_data: Dict) -> bool:
    """LLM 호출이 필요한지 판단한다.

    조건: 상충 시그널(매수+매도 혼재) 또는 합류 점수 >= 2
    """
    signals = stock_data.get("signals", [])
    if not signals:
        return False

    types = set(s["type"] for s in signals)
    has_conflict = "buy" in types and "sell" in types

    score = stock_data.get("confluence_score", 0)

    return has_conflict or score >= 2
