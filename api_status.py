"""
api_status.py — 외부 API(Google Search / Gemini / Claude) 연결 상태 점검.

- 5분 간격으로 캐시(`st.cache_data(ttl=300)`)하여 매 rerun 시 비용·지연을 줄인다.
- 키 미설정 / 인증 실패 / 쿼터 초과 / 네트워크 오류를 구분해 상태값을 반환한다.
- 상단 바(render_api_status_bar)에서 색상 칩(녹/황/적)으로 노출한다.

상태값
    ok    : 정상 (녹색)
    warn  : 키 미설정 / 쿼터 임박 (노랑)
    error : 인증 실패 / 연결 실패 / 토큰 소진 (빨강)
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Tuple, Dict

import requests
import streamlit as st

try:
    from logging_setup import get_logger
    _log = get_logger("API_STATUS")
except Exception:
    import logging
    _log = logging.getLogger("api_status")

_HTTP_TIMEOUT = 6  # seconds


# ---------------------------------------------------------------------------
# 개별 점검 함수
# ---------------------------------------------------------------------------
def _check_gemini() -> Tuple[str, str]:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return ("warn", "키 미설정")
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": key, "pageSize": 1},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 200:
            return ("ok", "정상")
        if r.status_code in (401, 403):
            return ("error", "인증 실패(키)")
        if r.status_code == 429:
            return ("error", "쿼터/토큰 소진")
        return ("error", f"HTTP {r.status_code}")
    except requests.RequestException as e:
        _log.warning(f"Gemini ping 실패: {e}")
        return ("error", "연결 실패")


def _check_google_search() -> Tuple[str, str]:
    key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    cse = (os.getenv("GOOGLE_CSE_ID") or "").strip()
    if not key or not cse:
        return ("warn", "키/CSE 미설정")
    try:
        r = requests.get(
            "https://customsearch.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cse, "q": "ping", "num": 1},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 200:
            return ("ok", "정상")
        if r.status_code in (401, 403):
            return ("error", "인증 실패(키)")
        if r.status_code == 429:
            return ("error", "쿼터/토큰 소진")
        return ("error", f"HTTP {r.status_code}")
    except requests.RequestException as e:
        _log.warning(f"Google Search ping 실패: {e}")
        return ("error", "연결 실패")


def _check_claude() -> Tuple[str, str]:
    key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        return ("warn", "키 미설정")
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 200:
            return ("ok", "정상")
        if r.status_code in (401, 403):
            return ("error", "인증 실패(키)")
        if r.status_code == 429:
            return ("error", "쿼터/토큰 소진")
        return ("error", f"HTTP {r.status_code}")
    except requests.RequestException as e:
        _log.warning(f"Claude ping 실패: {e}")
        return ("error", "연결 실패")


# ---------------------------------------------------------------------------
# 통합 점검 (캐시)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def check_all_apis() -> Dict[str, Tuple[str, str]]:
    """외부 API 상태 점검. 5분 캐시.

    Gemini는 Pro/Flash 모두 동일한 API 키/엔드포인트를 공유하므로 한 번의 ping 결과를
    두 칩(Pro/Flash)에 공통으로 적용한다.
    """
    gemini_state = _check_gemini()
    return {
        "Gemini Pro": gemini_state,
        "Gemini Flash": gemini_state,
        "Google Search": _check_google_search(),
        "Claude": _check_claude(),
    }


def invalidate_cache() -> None:
    try:
        check_all_apis.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# UI 렌더링
# ---------------------------------------------------------------------------
_ICON = {"ok": "🟢", "warn": "🟡", "error": "🔴"}
_LABEL = {"ok": "정상", "warn": "경고", "error": "오류"}


@lru_cache(maxsize=1)
def _cse_version_label() -> str:
    """Google Custom Search API 디스커버리 문서에서 실제 사용중인 버전·리비전 조회.

    Custom Search JSON API는 v1만 발행되어 있으며(preferred=True), 디스커버리 문서의
    revision 값으로 스키마 갱신일을 함께 보여준다. 네트워크 오류 시 'v1'만 표시.
    """
    try:
        import urllib.request, json
        with urllib.request.urlopen(
            "https://customsearch.googleapis.com/$discovery/rest?version=v1",
            timeout=4,
        ) as r:
            d = json.loads(r.read())
        rev = d.get("revision") or ""
        ver = d.get("version") or "v1"
        # revision: YYYYMMDD → YYYY-MM-DD
        if len(rev) == 8 and rev.isdigit():
            rev = f"{rev[:4]}-{rev[4:6]}-{rev[6:]}"
        return f"Custom Search {ver} · rev {rev}" if rev else f"Custom Search {ver}"
    except Exception:
        return "Custom Search v1"


def _service_model_map() -> dict:
    """서비스명 → 표시할 모델/버전 라벨. 별칭은 실제 resolve된 버전과 함께 표시."""
    try:
        from llm_config import (
            gemini_pro_model,
            gemini_flash_model,
            claude_model,
            resolve_gemini_version,
        )

        def _gemini_label(alias: str) -> str:
            resolved = resolve_gemini_version(alias)
            if resolved and resolved != alias:
                return f"{alias} → {resolved}"
            return alias

        return {
            "Gemini Pro": _gemini_label(gemini_pro_model()),
            "Gemini Flash": _gemini_label(gemini_flash_model()),
            "Claude": claude_model(),
            # Google Custom Search JSON API는 v1만 발행됨 (디스커버리에서 실제 revision 조회)
            "Google Search": _cse_version_label(),
        }
    except Exception:
        return {}


def render_api_status_bar() -> None:
    """페이지 상단 API 상태 바. 오류·경고가 있으면 추가 알림 배너도 출력.

    각 서비스 칩에는 상태(🟢/🟡/🔴) + 서비스명 + 상태 메시지 + 현재 연결된 모델 버전을 함께 표시.
    """
    statuses = check_all_apis()
    models = _service_model_map()

    pills = []
    for svc, (state, msg) in statuses.items():
        model_id = models.get(svc, "")
        # 정상(ok) 상태일 때만 모델 버전을 강조 표시. 오류/경고 시는 메시지에 집중.
        model_html = (
            f'<span class="appx-api-model" title="현재 연결된 모델/버전">⚙ {model_id}</span>'
            if (state == "ok" and model_id) else ""
        )
        pills.append(
            f'<span class="appx-api-pill appx-api-{state}">'
            f'<span class="appx-api-dot">{_ICON.get(state, "⚪")}</span>'
            f'<span class="appx-api-name">{svc}</span>'
            f'<span class="appx-api-msg">{msg}</span>'
            f'{model_html}'
            f'</span>'
        )
    bar_html = (
        '<div class="appx-api-bar">'
        '<span class="appx-api-bar-title">외부 API 상태</span>'
        f'{"".join(pills)}'
        '</div>'
    )
    st.markdown(bar_html, unsafe_allow_html=True)

    # 2) 경고/오류 배너
    errors = [svc for svc, (s, _) in statuses.items() if s == "error"]
    warns = [svc for svc, (s, _) in statuses.items() if s == "warn"]

    if errors:
        detail = ", ".join(f"{svc}({statuses[svc][1]})" for svc in errors)
        st.error(
            f"⚠️ 외부 API 연결 오류: **{detail}** — 해당 기능은 정상 동작하지 않을 수 있습니다. "
            f"API 키 / 쿼터 / 네트워크 상태를 확인하세요."
        )
    elif warns:
        detail = ", ".join(f"{svc}({statuses[svc][1]})" for svc in warns)
        st.warning(
            f"⚠️ 일부 API 미설정/경고: **{detail}** — .env 파일에서 키를 설정하면 자동 활성화됩니다."
        )

    # 3) 새로고침 버튼 (캐시 무효화)
    if st.button("🔄 API 상태 새로고침", key="appx_api_refresh_btn", help="캐시(5분)를 비우고 다시 점검합니다."):
        invalidate_cache()
        st.rerun()
