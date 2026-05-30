"""
llm_config.py — Gemini / Claude 모델명 단일 설정.

원칙
- 하드코딩된 모델명을 코드 전반에 흩뿌리지 않는다.
- Google이 공식 운영하는 "always-latest" 별칭(`gemini-pro-latest`, `gemini-flash-latest`)을
  기본값으로 사용해 신규 모델 출시 시 자동 반영되도록 한다.
- 사용자는 .env에서 모델명을 직접 고정/변경할 수 있다.

환경변수
- GEMINI_PRO_MODEL    (default: "gemini-pro-latest")    — 본문/품질강화/검증 등 고난이도 작업
- GEMINI_FLASH_MODEL  (default: "gemini-flash-latest")  — 목차 추출/요약 등 빠른 작업
- CLAUDE_MODEL        (default: "claude-opus-4-5")      — PPT 슬라이드 생성
"""
from __future__ import annotations
import os

DEFAULT_GEMINI_PRO = "gemini-pro-latest"
DEFAULT_GEMINI_FLASH = "gemini-flash-latest"
DEFAULT_CLAUDE = "claude-opus-4-5"


def gemini_pro_model() -> str:
    return (os.getenv("GEMINI_PRO_MODEL") or DEFAULT_GEMINI_PRO).strip()


def gemini_flash_model() -> str:
    return (os.getenv("GEMINI_FLASH_MODEL") or DEFAULT_GEMINI_FLASH).strip()


def claude_model() -> str:
    return (os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE).strip()


def get_active_models() -> dict:
    """현재 사용 중인 모델 식별자 (UI 표시·로그용)."""
    return {
        "Gemini Pro": gemini_pro_model(),
        "Gemini Flash": gemini_flash_model(),
        "Claude": claude_model(),
    }
