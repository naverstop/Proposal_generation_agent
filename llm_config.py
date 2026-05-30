"""
llm_config.py — Gemini / Claude 모델명 단일 설정.

원칙
- 하드코딩된 모델명을 코드 전반에 흩뿌리지 않는다.
- Google이 공식 운영하는 "always-latest" 별칭(`gemini-pro-latest`, `gemini-flash-latest`)을
  Gemini 기본값으로 사용해 신규 모델 출시 시 자동 반영되도록 한다.
- Anthropic은 `*-latest` 별칭을 제공하지 않으므로, models.list() API를 호출해
  가장 최신의 Opus(혹은 폴백으로 Sonnet) 모델을 1시간 캐시로 자동 디스커버리한다.
- 사용자는 .env에서 모델명을 직접 고정/변경할 수 있다 (디스커버리보다 우선).

환경변수
- GEMINI_PRO_MODEL    (default: "gemini-pro-latest")   — 본문/품질강화/검증 등 고난이도 작업
- GEMINI_FLASH_MODEL  (default: "gemini-flash-latest") — 목차 추출/요약 등 빠른 작업
- CLAUDE_MODEL        (default: 자동 디스커버리 또는 "claude-opus-4-8") — PPT 슬라이드 생성
- CLAUDE_TIER         (default: "opus") — 자동 디스커버리 대상 티어. opus|sonnet|haiku
"""
from __future__ import annotations
import os
import time
from typing import Optional

try:
    from logging_setup import get_logger
    _log = get_logger("LLM_CONFIG")
except Exception:
    import logging
    _log = logging.getLogger("llm_config")

DEFAULT_GEMINI_PRO = "gemini-pro-latest"
DEFAULT_GEMINI_FLASH = "gemini-flash-latest"
DEFAULT_CLAUDE_FALLBACK = "claude-opus-4-8"  # API 디스커버리 실패 시 안전 기본값 (현재 최신 stable)

# 디스커버리 결과 캐시 (1시간)
_CLAUDE_CACHE: dict = {"model": None, "ts": 0.0}
_CLAUDE_CACHE_TTL = 3600  # 1h


def gemini_pro_model() -> str:
    return (os.getenv("GEMINI_PRO_MODEL") or DEFAULT_GEMINI_PRO).strip()


def gemini_flash_model() -> str:
    return (os.getenv("GEMINI_FLASH_MODEL") or DEFAULT_GEMINI_FLASH).strip()


def _discover_latest_claude(tier: str = "opus") -> Optional[str]:
    """Anthropic /v1/models를 호출해 주어진 티어의 최신 모델 ID를 반환.

    선택 규칙:
      1) id에 `claude-{tier}` 포함
      2) id 끝에 -YYYYMMDD 타임스탬프가 없는 "stable" 식별자 우선 (예: claude-opus-4-8)
      3) 동률이면 created_at 최신
    """
    api_key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        import requests
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            params={"limit": 100},
            timeout=6,
        )
        if r.status_code != 200:
            _log.warning(f"Anthropic models.list HTTP {r.status_code}")
            return None
        models = r.json().get("data", [])
        tier_l = tier.lower()
        candidates = [m for m in models if f"claude-{tier_l}" in (m.get("id") or "")]
        if not candidates:
            return None

        def _is_stable(mid: str) -> int:
            # id 끝 -YYYYMMDD 형식이면 스냅샷, 아니면 stable alias
            tail = mid.rsplit("-", 1)[-1]
            return 0 if (len(tail) == 8 and tail.isdigit()) else 1

        candidates.sort(
            key=lambda m: (_is_stable(m.get("id", "")), m.get("created_at", "")),
            reverse=True,
        )
        chosen = candidates[0].get("id")
        _log.info(f"Claude auto-discovered latest {tier_l}: {chosen}")
        return chosen
    except Exception as e:
        _log.warning(f"Claude 자동 디스커버리 실패: {type(e).__name__}: {e}")
        return None


def claude_model() -> str:
    """현재 사용할 Claude 모델 ID 반환.

    우선순위:
      1) .env CLAUDE_MODEL이 명시되어 있으면 그대로 사용 (override)
      2) /v1/models 호출 결과 중 가장 최신 stable 모델 (1h 캐시)
      3) 안전 기본값 (DEFAULT_CLAUDE_FALLBACK)
    """
    explicit = (os.getenv("CLAUDE_MODEL") or "").strip()
    if explicit:
        return explicit

    now = time.time()
    if _CLAUDE_CACHE["model"] and (now - _CLAUDE_CACHE["ts"] < _CLAUDE_CACHE_TTL):
        return _CLAUDE_CACHE["model"]

    tier = (os.getenv("CLAUDE_TIER") or "opus").strip().lower()
    discovered = _discover_latest_claude(tier)
    chosen = discovered or DEFAULT_CLAUDE_FALLBACK
    _CLAUDE_CACHE["model"] = chosen
    _CLAUDE_CACHE["ts"] = now
    return chosen


def invalidate_claude_cache() -> None:
    _CLAUDE_CACHE["model"] = None
    _CLAUDE_CACHE["ts"] = 0.0


# ---------------------------------------------------------------------------
# Gemini 별칭(latest) → 실제 resolve 버전 조회
# ---------------------------------------------------------------------------
# 별칭은 자기 자신만 echo하므로(`gemini-pro-latest` → "Gemini Pro Latest"),
# `:generateContent` 응답의 `modelVersion` 필드를 캡처해야 실제 버전(예: gemini-3.1-pro-preview)을 얻을 수 있다.
_GEMINI_RESOLVED_CACHE: dict = {}  # alias -> {"version": str, "ts": float}
_GEMINI_RESOLVED_TTL = 3600  # 1h


def resolve_gemini_version(model_id: str) -> str:
    """모델 ID가 *-latest 별칭이면 실제 resolve된 버전 ID를 반환, 그렇지 않으면 자기 자신 반환.

    Google Generative Language API는 별칭의 실제 매핑을 메타데이터로 노출하지 않아,
    1토큰짜리 generateContent 호출로 `modelVersion` 필드를 캡처한다. 1시간 캐시.
    """
    if not model_id or "latest" not in model_id:
        return model_id
    now = time.time()
    cached = _GEMINI_RESOLVED_CACHE.get(model_id)
    if cached and (now - cached["ts"] < _GEMINI_RESOLVED_TTL):
        return cached["version"]

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return model_id
    try:
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        body = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 1},
        }
        r = requests.post(url, params={"key": api_key}, json=body, timeout=6)
        if r.status_code != 200:
            return model_id
        resolved = (r.json().get("modelVersion") or "").strip() or model_id
        _GEMINI_RESOLVED_CACHE[model_id] = {"version": resolved, "ts": now}
        _log.info(f"Gemini alias resolved: {model_id} → {resolved}")
        return resolved
    except Exception as e:
        _log.warning(f"Gemini resolve 실패 ({model_id}): {type(e).__name__}: {e}")
        # 실패도 짧게(60초) 캐시하여 SSL 일시 오류 시 호출 폭주 방지.
        _GEMINI_RESOLVED_CACHE[model_id] = {"version": model_id, "ts": now - (_GEMINI_RESOLVED_TTL - 60)}
        return model_id


def invalidate_gemini_resolve_cache() -> None:
    _GEMINI_RESOLVED_CACHE.clear()


def get_active_models() -> dict:
    """현재 사용 중인 모델 식별자 (UI 표시·로그용)."""
    return {
        "Gemini Pro": gemini_pro_model(),
        "Gemini Flash": gemini_flash_model(),
        "Claude": claude_model(),
    }
