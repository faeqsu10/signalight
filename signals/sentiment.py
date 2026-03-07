import json
import logging
import os
from typing import Dict, List, Optional

import requests

from config import (
    GOOGLE_API_KEY,
    SENTIMENT_MODEL,
    SENTIMENT_TEMPERATURE,
    SENTIMENT_MAX_TOKENS,
    SENTIMENT_TIMEOUT,
)

logger = logging.getLogger(__name__)


def analyze_sentiment(
    headlines: List[str],
    ticker_name: str,
) -> Optional[Dict]:
    """뉴스 헤드라인을 분석하여 감성 결과를 반환한다.

    Google Gemini REST API를 사용하여 뉴스 헤드라인의 감성을 분석한다.

    Args:
        headlines: 뉴스 제목 리스트 (최대 5개)
        ticker_name: 종목명 (예: "삼성전자")

    Returns:
        dict: {
            "sentiment": "긍정" | "부정" | "중립",
            "score": float (-1.0 ~ 1.0),
            "summary": str (한줄 요약),
            "confidence": float (0.0 ~ 1.0)
        }
        또는 API 키 없거나 실패 시 None
    """
    if not GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다. 감성 분석을 건너뜁니다.")
        return None

    if not headlines:
        logger.warning("헤드라인 리스트가 비어 있습니다.")
        return None

    try:
        # 최대 5개로 제한
        selected = headlines[:5]
        headline_lines = "\n".join(
            f"{i + 1}. {h}" for i, h in enumerate(selected)
        )

        prompt = (
            "당신은 한국 주식 시장 뉴스 감성 분석 전문가입니다.\n"
            "주어진 뉴스 헤드라인을 분석하여 해당 종목에 대한 감성을 판단하세요.\n"
            '반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이 JSON만):\n'
            '{"sentiment": "긍정|부정|중립", "score": -1.0~1.0, '
            '"summary": "한줄요약", "confidence": 0.0~1.0}\n\n'
            f"종목: {ticker_name}\n"
            f"최근 뉴스 헤드라인:\n"
            f"{headline_lines}\n\n"
            f"이 뉴스들을 종합하여 {ticker_name}에 대한 시장 감성을 분석해주세요."
        )

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{SENTIMENT_MODEL}:generateContent"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": SENTIMENT_TEMPERATURE,
                "maxOutputTokens": SENTIMENT_MAX_TOKENS,
            },
        }

        resp = requests.post(
            url,
            params={"key": GOOGLE_API_KEY},
            json=payload,
            timeout=SENTIMENT_TIMEOUT,
        )
        resp.raise_for_status()

        result = resp.json()
        # Gemini 2.5 Flash thinking 모델은 여러 parts를 반환할 수 있음
        # thought=True인 파트를 건너뛰고 실제 응답 텍스트를 찾는다
        parts = result["candidates"][0]["content"]["parts"]
        raw_text = ""
        for part in parts:
            if part.get("thought"):
                continue
            raw_text = part.get("text", "").strip()
            if raw_text:
                break
        if not raw_text:
            # fallback: 마지막 파트 사용
            raw_text = parts[-1].get("text", "").strip()

        # 마크다운 코드블록 제거 (```json ... ```)
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            # 첫 줄(```json)과 마지막 줄(```) 제거
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_text = "\n".join(lines).strip()

        # JSON 추출 (응답에 다른 텍스트가 섞여 있을 경우 대비)
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("Gemini 응답에서 JSON을 찾을 수 없습니다: %s", raw_text)
            return None

        data = json.loads(raw_text[start:end])

        # 필수 필드 검증
        required_keys = {"sentiment", "score", "summary", "confidence"}
        if not required_keys.issubset(data.keys()):
            logger.error("Gemini 응답 JSON에 필수 필드가 누락되었습니다: %s", data)
            return None

        # score 클램핑 (-1.0 ~ 1.0)
        data["score"] = max(-1.0, min(1.0, float(data["score"])))

        # confidence 클램핑 (0.0 ~ 1.0)
        data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))

        return data

    except Exception as e:
        logger.error("감성 분석 중 오류 발생: %s", e)
        return None
