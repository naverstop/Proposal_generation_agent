"""
ui_theme.py — 전 페이지 공통 디자인 토큰 / CSS / UI 헬퍼.

- inject_global_css()  : 페이지 최상단에서 1회 호출. Pretendard 로드, 컬러 토큰,
                         버튼/입력/카드/탭/사이드바/알림 스타일, 모바일 반응형 미디어쿼리 적용.
- render_stepper(...)  : 5단계 마법사 진행 상태를 표시하는 가로 스테퍼.
- status_badge(...)    : 상태 배지 HTML 문자열 반환 (완료/진행중/대기/오류).
- page_header(...)     : 타이틀/서브타이틀/우측 메타를 한 줄로 정리.

설계 원칙
- "디자인 토큰을 단일 파일에 둔다" → 색·간격·반경을 :root CSS 변수로 노출.
- "모바일에서 깨지지 않는다" → @media (max-width: 768px)에서 radio 5탭이 가로 스크롤 가능 grid로 전환.
- "Streamlit 다크모드"에 자동 대응 → prefers-color-scheme 미디어쿼리로 토큰 재정의.
"""
from __future__ import annotations
import streamlit as st


_BOOT_KEY = "_ui_theme_injected"


def inject_global_css() -> None:
    """모든 페이지에서 최상단 1회 호출. Streamlit은 매 rerun마다 DOM을 새로 만드므로
    매 실행마다 다시 주입해야 한다 (세션 가드를 두지 않는다)."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", meta: str = "") -> None:
    """앱 상단 타이틀 영역. 버전 라벨 등은 우측 meta로 분리해서 노출."""
    meta_html = f'<div class="appx-header-meta">{meta}</div>' if meta else ""
    sub_html = f'<p class="appx-header-sub">{subtitle}</p>' if subtitle else ""
    html = (
        f'<div class="appx-header">'
        f'<div class="appx-header-text">'
        f'<h1 class="appx-header-title">{title}</h1>'
        f'{sub_html}'
        f'</div>'
        f'{meta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def status_badge(label: str, kind: str = "neutral") -> str:
    """상태 배지 HTML. kind ∈ {success, info, warning, danger, neutral}."""
    kind = kind if kind in ("success", "info", "warning", "danger", "neutral") else "neutral"
    return f'<span class="appx-badge appx-badge-{kind}">{label}</span>'


def render_stepper(steps: list[str], current_index: int, completed: set[int] | None = None,
                   errors: set[int] | None = None) -> None:
    """가로 스테퍼. 모바일에서는 가로 스크롤로 전환된다.
    steps          : 단계 라벨 리스트
    current_index  : 현재 활성 단계 인덱스 (0-base)
    completed      : 완료된 단계 인덱스 집합
    errors         : 오류가 발생한 단계 인덱스 집합
    """
    completed = completed or set()
    errors = errors or set()
    parts = []
    for i, label in enumerate(steps):
        if i in errors:
            state = "error"
            icon = "!"
        elif i in completed:
            state = "done"
            icon = "✓"
        elif i == current_index:
            state = "current"
            icon = str(i + 1)
        else:
            state = "todo"
            icon = str(i + 1)
        parts.append(
            f'<div class="appx-step appx-step-{state}"><div class="appx-step-dot">{icon}</div><div class="appx-step-label">{label}</div></div>'
        )
        if i < len(steps) - 1:
            line_state = "done" if (i in completed and (i + 1) in completed or i in completed) else "todo"
            parts.append(f'<div class="appx-step-line appx-step-line-{line_state}"></div>')
    st.markdown(
        f'<div class="appx-stepper">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 글로벌 CSS — 디자인 토큰 + 컴포넌트 + 모바일 반응형
# ---------------------------------------------------------------------------
_GLOBAL_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
:root {
    /* Color tokens */
    --appx-bg: #F8FAFC;
    --appx-surface: #FFFFFF;
    --appx-surface-2: #F1F5F9;
    --appx-border: #E2E8F0;
    --appx-border-strong: #CBD5E1;
    --appx-text: #0F172A;
    --appx-text-muted: #64748B;
    --appx-primary: #2563EB;
    --appx-primary-hover: #1D4ED8;
    --appx-primary-soft: #DBEAFE;
    --appx-success: #10B981;
    --appx-success-soft: #D1FAE5;
    --appx-warning: #F59E0B;
    --appx-warning-soft: #FEF3C7;
    --appx-danger: #EF4444;
    --appx-danger-soft: #FEE2E2;
    --appx-info: #0EA5E9;
    --appx-info-soft: #E0F2FE;
    /* Spacing & radius */
    --appx-radius-sm: 6px;
    --appx-radius-md: 10px;
    --appx-radius-lg: 14px;
    --appx-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06);
    --appx-shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.06), 0 2px 4px -2px rgba(15, 23, 42, 0.06);
}

/* Dark mode auto-detect (Streamlit 다크 테마와도 어울리도록) */
@media (prefers-color-scheme: dark) {
    :root {
        --appx-bg: #0B1220;
        --appx-surface: #111827;
        --appx-surface-2: #1F2937;
        --appx-border: #1F2937;
        --appx-border-strong: #374151;
        --appx-text: #F1F5F9;
        --appx-text-muted: #94A3B8;
        --appx-primary: #60A5FA;
        --appx-primary-hover: #3B82F6;
        --appx-primary-soft: #1E3A8A;
        --appx-success-soft: #064E3B;
        --appx-warning-soft: #78350F;
        --appx-danger-soft: #7F1D1D;
        --appx-info-soft: #075985;
    }
}

/* Base */
html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stTitle {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important;
}
.stApp { background-color: var(--appx-bg) !important; }

/* 컨텐츠 컨테이너 최대폭 — 가독성 */
.main .block-container { max-width: 1180px; padding-top: 1.6rem; padding-bottom: 3rem; }

/* App header (page_header helper) */
.appx-header {
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 1rem; margin-bottom: 0.4rem;
}
.appx-header-title {
    font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; color: var(--appx-text);
    margin: 0;
}
.appx-header-sub { color: var(--appx-text-muted); font-size: 0.95rem; margin: 4px 0 0 0; }
.appx-header-meta {
    color: var(--appx-text-muted); font-size: 0.78rem; font-family: ui-monospace, Menlo, monospace;
    white-space: nowrap;
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: var(--appx-radius-md) !important;
    border: 1px solid var(--appx-border) !important;
    background: var(--appx-surface) !important;
    color: var(--appx-text) !important;
    font-weight: 600 !important;
    padding: 0.55rem 1rem !important;
    transition: all 0.15s ease;
    box-shadow: var(--appx-shadow-sm);
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: var(--appx-primary) !important;
    color: var(--appx-primary) !important;
    transform: translateY(-1px);
}
.stButton > button:focus, .stDownloadButton > button:focus {
    outline: 2px solid var(--appx-primary) !important; outline-offset: 2px;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: var(--appx-primary) !important;
    border-color: var(--appx-primary) !important;
    color: #FFFFFF !important;
    box-shadow: 0 6px 14px -4px rgba(37, 99, 235, 0.45);
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
    background: var(--appx-primary-hover) !important;
    border-color: var(--appx-primary-hover) !important;
    color: #FFFFFF !important;
}
.stButton > button:disabled {
    opacity: 0.55 !important; cursor: not-allowed !important; transform: none !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div {
    border-radius: var(--appx-radius-md) !important;
    border: 1px solid var(--appx-border) !important;
    background: var(--appx-surface) !important;
    color: var(--appx-text) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--appx-primary) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

/* Radio tab navigation (메인 5단계 탭) */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex; justify-content: center; gap: 8px;
    margin-bottom: 24px; margin-top: -28px;
    flex-wrap: nowrap; overflow-x: auto;
    scrollbar-width: thin;
    padding-bottom: 4px;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--appx-surface); color: var(--appx-text-muted);
    padding: 10px 14px; margin: 0;
    border: 1px solid var(--appx-border);
    border-radius: var(--appx-radius-md);
    cursor: pointer; transition: all 0.18s ease;
    font-weight: 600; flex-grow: 1; text-align: center;
    box-shadow: var(--appx-shadow-sm);
    white-space: nowrap;
    min-width: 140px;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child { display: none; }
div[data-testid="stRadio"] > div[role="radiogroup"] > label[aria-checked="true"] {
    background: var(--appx-primary) !important;
    color: #FFFFFF !important;
    border-color: var(--appx-primary) !important;
    box-shadow: 0 6px 14px -4px rgba(37, 99, 235, 0.45) !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:not([aria-checked="true"]):hover {
    background: var(--appx-primary-soft);
    color: var(--appx-primary-hover);
    border-color: var(--appx-primary);
}

/* Alerts — Streamlit 기본 알림 박스 톤 다듬기 */
div[data-testid="stAlert"] {
    border-radius: var(--appx-radius-md) !important;
    border: 1px solid var(--appx-border) !important;
    box-shadow: var(--appx-shadow-sm);
}

/* Expander */
div[data-testid="stExpander"] {
    border: 1px solid var(--appx-border) !important;
    border-radius: var(--appx-radius-md) !important;
    background: var(--appx-surface) !important;
    box-shadow: var(--appx-shadow-sm);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--appx-surface) !important;
    border-right: 1px solid var(--appx-border);
}
section[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--appx-text-muted); margin-top: 1.2rem; margin-bottom: 0.4rem;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--appx-border); border-radius: var(--appx-radius-md); overflow: hidden;
}

/* Badges */
.appx-badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.02em;
    border: 1px solid transparent;
}
.appx-badge-success { background: var(--appx-success-soft); color: var(--appx-success); border-color: var(--appx-success); }
.appx-badge-info    { background: var(--appx-info-soft);    color: var(--appx-info);    border-color: var(--appx-info); }
.appx-badge-warning { background: var(--appx-warning-soft); color: var(--appx-warning); border-color: var(--appx-warning); }
.appx-badge-danger  { background: var(--appx-danger-soft);  color: var(--appx-danger);  border-color: var(--appx-danger); }
.appx-badge-neutral { background: var(--appx-surface-2);    color: var(--appx-text-muted); border-color: var(--appx-border-strong); }

/* Stepper */
.appx-stepper {
    display: flex; align-items: center; gap: 4px;
    padding: 14px 18px; margin: 4px 0 18px 0;
    background: var(--appx-surface); border: 1px solid var(--appx-border);
    border-radius: var(--appx-radius-lg); box-shadow: var(--appx-shadow-sm);
    overflow-x: auto; scrollbar-width: thin;
}
.appx-step { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.appx-step-dot {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.85rem;
    background: var(--appx-surface-2); color: var(--appx-text-muted);
    border: 1px solid var(--appx-border-strong);
}
.appx-step-label { font-size: 0.85rem; font-weight: 600; color: var(--appx-text-muted); }
.appx-step-current .appx-step-dot {
    background: var(--appx-primary); color: #FFFFFF; border-color: var(--appx-primary);
    box-shadow: 0 0 0 4px var(--appx-primary-soft);
}
.appx-step-current .appx-step-label { color: var(--appx-text); }
.appx-step-done .appx-step-dot {
    background: var(--appx-success); color: #FFFFFF; border-color: var(--appx-success);
}
.appx-step-done .appx-step-label { color: var(--appx-text); }
.appx-step-error .appx-step-dot {
    background: var(--appx-danger); color: #FFFFFF; border-color: var(--appx-danger);
}
.appx-step-error .appx-step-label { color: var(--appx-danger); }
.appx-step-line {
    flex: 1; min-width: 18px; height: 2px;
    background: var(--appx-border-strong);
    border-radius: 999px;
}
.appx-step-line-done { background: var(--appx-success); }

/* API Status Bar */
.appx-api-bar {
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
    padding: 10px 14px; margin: -4px 0 14px 0;
    background: var(--appx-surface); border: 1px solid var(--appx-border);
    border-radius: var(--appx-radius-lg); box-shadow: var(--appx-shadow-sm);
}
.appx-api-bar-title {
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase; color: var(--appx-text-muted);
    padding-right: 6px; border-right: 1px solid var(--appx-border-strong);
    margin-right: 4px;
}
.appx-api-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 999px;
    font-size: 0.82rem; font-weight: 600;
    border: 1px solid transparent;
    background: var(--appx-surface-2);
}
.appx-api-name { font-weight: 700; color: var(--appx-text); }
.appx-api-msg { color: var(--appx-text-muted); font-size: 0.78rem; }
.appx-api-dot { font-size: 0.7rem; line-height: 1; }
.appx-api-ok    { background: var(--appx-success-soft); border-color: var(--appx-success); }
.appx-api-ok .appx-api-msg { color: var(--appx-success); }
.appx-api-warn  { background: var(--appx-warning-soft); border-color: var(--appx-warning); }
.appx-api-warn .appx-api-msg { color: var(--appx-warning); }
.appx-api-error { background: var(--appx-danger-soft); border-color: var(--appx-danger); }
.appx-api-error .appx-api-msg { color: var(--appx-danger); font-weight: 700; }

/* Active model chips (under API bar) */
.appx-model-bar {
    display: flex; flex-wrap: wrap; gap: 6px;
    margin: -8px 0 14px 0;
    padding: 0 2px;
}
.appx-model-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 999px;
    font-size: 0.72rem; color: var(--appx-text-muted);
    background: var(--appx-surface-2); border: 1px solid var(--appx-border);
}
.appx-model-chip b { color: var(--appx-text); font-weight: 700; }

/* Login hero */
.appx-login-hero {
    background: linear-gradient(135deg, #2563EB 0%, #7C3AED 100%);
    color: #FFFFFF;
    border-radius: var(--appx-radius-lg);
    padding: 28px 32px;
    margin-bottom: 22px;
    box-shadow: 0 12px 30px -10px rgba(37, 99, 235, 0.5);
}
.appx-login-hero h1 { color: #FFFFFF; margin: 0 0 6px 0; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; }
.appx-login-hero p  { color: rgba(255, 255, 255, 0.92); margin: 0; font-size: 0.95rem; }

/* Mobile responsive */
@media (max-width: 768px) {
    .main .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
    .appx-header { flex-direction: column; align-items: flex-start; gap: 4px; }
    .appx-header-title { font-size: 1.35rem; }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        margin-top: -10px; justify-content: flex-start;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        min-width: 130px; padding: 8px 10px; font-size: 0.85rem; flex-grow: 0;
    }
    .appx-stepper { padding: 10px 12px; gap: 2px; }
    .appx-step-label { display: none; }
    .appx-step-current .appx-step-label,
    .appx-step-error .appx-step-label { display: inline; }
    .appx-step-line { min-width: 12px; }
    .stButton > button, .stDownloadButton > button { width: 100% !important; padding: 0.65rem 0.8rem !important; }
    .appx-login-hero { padding: 18px 18px; }
    .appx-login-hero h1 { font-size: 1.3rem; }
}
@media (max-width: 480px) {
    .appx-header-title { font-size: 1.2rem; }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label { min-width: 120px; font-size: 0.8rem; }
}
</style>
"""
