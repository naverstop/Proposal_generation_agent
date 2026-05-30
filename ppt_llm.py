"""
ppt_llm.py — PPT 생성에 사용할 LLM 선택 로직.

우선순위
  1. CLAUDE_API_KEY(또는 ANTHROPIC_API_KEY)가 설정되어 있으면 Claude 최신 모델 사용.
     - 모델명은 CLAUDE_MODEL 환경변수로 오버라이드 가능. 기본값: "claude-opus-4-5".
     - (참고) 사용자가 "Claude 4.8"을 원할 경우 .env에 CLAUDE_MODEL=claude-opus-4-8 등으로
       지정하면 즉시 적용된다. Anthropic이 신규 모델 ID를 공개하면 환경변수만 바꾸면 된다.
  2. 위가 실패하거나 키가 없으면 Gemini (gemini-2.5-pro)로 fallback.

반환값: (llm_instance, display_name)
"""
from __future__ import annotations
import os
from typing import Tuple

try:
    from logging_setup import get_logger
    _log = get_logger("PPT_LLM")
except Exception:
    import logging
    _log = logging.getLogger("ppt_llm")


DEFAULT_CLAUDE_MODEL = "claude-opus-4-5"


def get_ppt_llm(gemini_api_key: str, max_retries: int = 1, temperature: float = 0.5) -> Tuple[object, str]:
    """PPT 생성용 LLM을 반환. Claude > Gemini 순으로 시도."""
    claude_key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    claude_model = (os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()

    if claude_key:
        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(
                model=claude_model,
                api_key=claude_key,
                temperature=temperature,
                max_tokens=4096,
                timeout=120,
                max_retries=max_retries,
            )
            _log.info(f"PPT LLM = Claude ({claude_model})")
            return llm, f"Claude · {claude_model}"
        except ImportError:
            _log.warning("langchain-anthropic 미설치 → pip install langchain-anthropic anthropic 필요. Gemini로 fallback.")
        except Exception as e:
            _log.warning(f"Claude 초기화 실패({e}) → Gemini로 fallback.")

    # Fallback: Gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=temperature,
        google_api_key=gemini_api_key,
        max_retries=max_retries,
    )
    _log.info("PPT LLM = Gemini (gemini-2.5-pro)")
    return llm, "Gemini · gemini-2.5-pro"
