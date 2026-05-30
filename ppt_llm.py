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


DEFAULT_CLAUDE_MODEL = "claude-opus-4-5"  # llm_config 자동 디스커버리 실패 시 safety net


def _temperature_deprecated(model_id: str) -> bool:
    """temperature 파라미터를 거부하는 신규 Claude 모델 식별.

    현재 Anthropic 정책상 Opus 4.8 이후의 reasoning/thinking 계열 모델이 해당된다.
    안전을 위해 'opus-4-8' 이상 패턴 또는 사용자가 명시한 _no_temp 접미사가 있으면 생략.
    """
    if not model_id:
        return False
    m = model_id.lower()
    # opus-4-8, opus-4-9, opus-5-x 등
    for known in ("opus-4-8", "opus-4-9", "opus-5"):
        if known in m:
            return True
    return False


def get_ppt_llm(gemini_api_key: str, max_retries: int = 1, temperature: float = 0.5) -> Tuple[object, str]:
    """PPT 생성용 LLM을 반환. Claude > Gemini 순으로 시도."""
    claude_key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    # llm_config.claude_model() 이 .env override + 자동 디스커버리(1h 캐시)를 모두 처리한다.
    try:
        from llm_config import claude_model as _claude_model_fn
        claude_model = _claude_model_fn()
    except Exception:
        claude_model = (os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()

    if claude_key:
        try:
            from langchain_anthropic import ChatAnthropic
            # 신규 Opus 4.8+ 등 일부 모델은 temperature 파라미터가 deprecated.
            # 4-8 이상 또는 사용자 지정 신 모델은 temperature 생략, 그 외는 종전대로 전달.
            kwargs = dict(
                model=claude_model,
                api_key=claude_key,
                max_tokens=4096,
                timeout=120,
                max_retries=max_retries,
            )
            if not _temperature_deprecated(claude_model):
                kwargs["temperature"] = temperature
            llm = ChatAnthropic(**kwargs)
            _log.info(f"PPT LLM = Claude ({claude_model})")
            return llm, f"Claude · {claude_model}"
        except ImportError:
            _log.warning("langchain-anthropic 미설치 → pip install langchain-anthropic anthropic 필요. Gemini로 fallback.")
        except Exception as e:
            _log.warning(f"Claude 초기화 실패({e}) → Gemini로 fallback.")

    # Fallback: Gemini (최신 안정 별칭 자동 적용)
    from langchain_google_genai import ChatGoogleGenerativeAI
    try:
        from llm_config import gemini_pro_model
        model_name = gemini_pro_model()
    except Exception:
        model_name = "gemini-pro-latest"
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=gemini_api_key,
        max_retries=max_retries,
    )
    _log.info(f"PPT LLM = Gemini ({model_name})")
    return llm, f"Gemini · {model_name}"
