"""
사용자 인증/승인 모듈.
- SQLite의 `users` 테이블을 단일 소스로 사용한다.
- 비밀번호는 PBKDF2-HMAC-SHA256 (260,000 라운드)으로 해싱한다.
- 관리자는 환경변수 ADMIN_EMAIL 또는 기본값 'orion0321@gmail.com' 한 명을 시드한다.
- 관리자도 비밀번호는 직접 설정한다(첫 로그인 시 본인이 입력).
- 일반 사용자는 회원가입 → status='pending' → 관리자 승인 후 status='approved'.
"""
import os
import sqlite3
import hashlib
import secrets
import datetime
import streamlit as st

try:
    from logging_setup import get_logger
    _log = get_logger("AUTH")
except Exception:
    import logging
    _log = logging.getLogger("auth")

# 쿠키 매니저(로그인 저장)는 선택 의존성 — 미설치 시에도 앱은 정상 동작한다.
try:
    import extra_streamlit_components as stx
    _HAS_COOKIES = True
except Exception:
    stx = None
    _HAS_COOKIES = False

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "orion0321@gmail.com").strip().lower()

PBKDF2_ITERATIONS = 260000
PBKDF2_ALGO = "sha256"

# 로그인 저장(자동 로그인) 설정
REMEMBER_COOKIE = "plan_agent_remember"
REMEMBER_DAYS = 30


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def _connect():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    return conn


def ensure_users_table():
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT,          -- NULL이면 아직 비밀번호 미설정(첫 로그인 시 설정)
            password_salt TEXT,
            status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected
            role TEXT NOT NULL DEFAULT 'user',      -- user | admin
            created_at TEXT NOT NULL,
            approved_at TEXT,
            approved_by TEXT,
            last_login_at TEXT,
            note TEXT
        )
        """
    )
    # 로그인 저장(자동 로그인)용 토큰 테이블 — 평문 토큰은 저장하지 않고 해시만 보관한다.
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token_hash TEXT PRIMARY KEY,
            email      TEXT NOT NULL COLLATE NOCASE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def seed_admin():
    """관리자 1명(orion0321@gmail.com)을 자동으로 시드/갱신한다. 비밀번호는 미설정 상태로 둔다."""
    ensure_users_table()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (ADMIN_EMAIL,))
    row = c.fetchone()
    if row is None:
        c.execute(
            "INSERT INTO users (email, status, role, created_at, approved_at, approved_by, note) "
            "VALUES (?, 'approved', 'admin', ?, ?, 'system', '초기 관리자')",
            (ADMIN_EMAIL, now, now),
        )
    else:
        # 항상 admin/approved 보장
        c.execute(
            "UPDATE users SET role='admin', status='approved' WHERE email = ? COLLATE NOCASE",
            (ADMIN_EMAIL,),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 비밀번호 해싱
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt: str) -> str:
    if not password:
        raise ValueError("비밀번호가 비어 있습니다.")
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return dk.hex()


def _new_salt() -> str:
    return secrets.token_hex(16)


def _set_password_for(email: str, password: str):
    salt = _new_salt()
    pw_hash = _hash_password(password, salt)
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET password_hash = ?, password_salt = ? WHERE email = ? COLLATE NOCASE",
        (pw_hash, salt, email),
    )
    conn.commit()
    conn.close()


def _verify_password(email: str, password: str) -> bool:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT password_hash, password_salt FROM users WHERE email = ? COLLATE NOCASE", (email,))
    row = c.fetchone()
    conn.close()
    if not row or not row["password_hash"] or not row["password_salt"]:
        return False
    return secrets.compare_digest(_hash_password(password, row["password_salt"]), row["password_hash"])


# ---------------------------------------------------------------------------
# 사용자 CRUD
# ---------------------------------------------------------------------------
def get_user(email: str):
    if not email:
        return None
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_users(status: str = None):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM users WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def register_user(email: str, password: str) -> tuple[bool, str]:
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email:
        return False, "올바른 이메일 형식이 아닙니다."
    if not password or len(password) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    ensure_users_table()
    if get_user(email):
        return False, "이미 등록된 이메일입니다. (승인 대기 중일 수 있음)"
    salt = _new_salt()
    pw_hash = _hash_password(password, salt)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (email, password_hash, password_salt, status, role, created_at) "
        "VALUES (?, ?, ?, 'pending', 'user', ?)",
        (email, pw_hash, salt, now),
    )
    conn.commit()
    conn.close()
    _log.info(f"회원가입 요청 접수 (승인대기): {email}")
    return True, "회원가입 요청이 접수되었습니다. 관리자 승인 후 사용 가능합니다."


def approve_user(email: str, by_admin: str) -> bool:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET status='approved', approved_at=?, approved_by=? WHERE email = ? COLLATE NOCASE",
        (now, by_admin, email),
    )
    changed = c.rowcount
    conn.commit()
    conn.close()
    if changed > 0:
        _log.info(f"승인: {email} by {by_admin}")
    return changed > 0


def reject_user(email: str, by_admin: str, note: str = "") -> bool:
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET status='rejected', approved_by=?, note=? WHERE email = ? COLLATE NOCASE",
        (by_admin, note or "rejected", email),
    )
    changed = c.rowcount
    conn.commit()
    conn.close()
    if changed > 0:
        _log.warning(f"거절: {email} by {by_admin}")
    return changed > 0


def delete_user(email: str) -> bool:
    if (email or "").strip().lower() == ADMIN_EMAIL:
        return False  # 관리자 본인 계정은 삭제 불가
    conn = _connect()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (email,))
    changed = c.rowcount
    conn.commit()
    conn.close()
    return changed > 0


# ---------------------------------------------------------------------------
# 로그인 저장(자동 로그인) — 쿠키 + 해시 토큰
# ---------------------------------------------------------------------------
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_remember_token(email: str) -> str:
    """평문 토큰을 발급하고 해시만 DB에 저장한다. 평문은 쿠키에만 보관된다."""
    ensure_users_table()
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.now()
    expires = now + datetime.timedelta(days=REMEMBER_DAYS)
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO auth_tokens (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), email.strip().lower(),
         now.strftime("%Y-%m-%d %H:%M:%S"), expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    # 만료 토큰 정리(주기적 청소 대용)
    c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (now.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()
    return token


def consume_remember_token(token: str) -> str | None:
    """유효한(미만료) 토큰이면 해당 이메일을 반환한다. 아니면 None."""
    if not token:
        return None
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT email, expires_at FROM auth_tokens WHERE token_hash = ?", (_hash_token(token),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        if datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.datetime.now():
            revoke_remember_token(token)
            return None
    except Exception:
        return None
    return row["email"]


def revoke_remember_token(token: str) -> None:
    if not token:
        return
    try:
        conn = _connect()
        c = conn.cursor()
        c.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (_hash_token(token),))
        conn.commit()
        conn.close()
    except Exception:
        pass


def build_cookie_manager():
    """매 스크립트 실행마다 CookieManager를 새로 생성해 쿠키를 다시 읽어온다.
    (CookieManager.get()은 생성 시점의 캐시를 읽으므로 인스턴스를 재사용하면
    최신 쿠키를 못 읽는다 → 실행당 1회 require_login에서만 호출한다.)"""
    if not _HAS_COOKIES:
        st.session_state["_cookie_manager"] = None
        return None
    try:
        cm = stx.CookieManager(key="plan_agent_cookies")
    except Exception:
        cm = None
    st.session_state["_cookie_manager"] = cm
    return cm


def get_cookie_manager():
    """현재 실행에서 build된 CookieManager를 반환(없으면 1회 생성). 미설치 시 None."""
    cm = st.session_state.get("_cookie_manager")
    if cm is None and _HAS_COOKIES:
        cm = build_cookie_manager()
    return cm


# ---------------------------------------------------------------------------
# 로그인 / 세션
# ---------------------------------------------------------------------------
def authenticate(email: str, password: str) -> tuple[bool, str, dict | None]:
    email = (email or "").strip().lower()
    user = get_user(email)
    if not user:
        _log.warning(f"로그인 실패 (미등록): {email}")
        return False, "등록되지 않은 이메일입니다.", None
    if user["status"] == "pending":
        _log.warning(f"로그인 차단 (승인대기): {email}")
        return False, "관리자 승인 대기 중입니다. 관리자에게 문의하세요.", None
    if user["status"] == "rejected":
        _log.warning(f"로그인 차단 (거절됨): {email}")
        return False, "가입이 거절되었습니다. 관리자에게 문의하세요.", None
    if not user["password_hash"]:
        _log.info(f"관리자 초기 비밀번호 미설정: {email}")
        return False, "초기 비밀번호가 설정되지 않았습니다. '관리자 초기 비밀번호 설정' 탭을 사용하세요.", None
    if not _verify_password(email, password):
        _log.warning(f"로그인 실패 (비밀번호 불일치): {email}")
        return False, "비밀번호가 일치하지 않습니다.", None
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE users SET last_login_at = ? WHERE email = ? COLLATE NOCASE", (now, email))
    conn.commit()
    conn.close()
    user["last_login_at"] = now
    _log.info(f"로그인 성공: {email} role={user['role']}")
    return True, "로그인 성공", user


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_admin() -> bool:
    u = current_user()
    return bool(u and u.get("role") == "admin")


def logout():
    # 자동 로그인 토큰/쿠키 정리
    try:
        cm = get_cookie_manager()
        token = cm.get(REMEMBER_COOKIE) if cm else None
        if token:
            revoke_remember_token(token)
        if cm:
            cm.delete(REMEMBER_COOKIE, key="logout_del_remember")
    except Exception:
        pass
    for k in ("auth_user", "auth_login_time"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# UI 가드
# ---------------------------------------------------------------------------
def _render_login_form():
    st.subheader("🔐 로그인")
    # 직전에 '로그인 저장'으로 저장해 둔 이메일이 있으면 미리 채워 준다.
    saved_email = ""
    try:
        cm = get_cookie_manager()
        if cm:
            saved_email = cm.get("plan_agent_email") or ""
    except Exception:
        saved_email = ""
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("이메일", value=saved_email, key="login_email").strip().lower()
        password = st.text_input("비밀번호", type="password", key="login_password")
        remember = st.checkbox(
            "로그인 저장 (이 브라우저에서 30일간 자동 로그인)",
            value=bool(saved_email),
            key="login_remember",
        )
        submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")
        if submitted:
            ok, msg, user = authenticate(email, password)
            if ok:
                st.session_state.auth_user = user
                st.session_state.auth_login_time = datetime.datetime.now().isoformat()
                # 로그인 저장 처리: 자동 로그인 토큰 + 이메일 쿠키 발급/삭제
                try:
                    cm = get_cookie_manager()
                    if cm:
                        expires = datetime.datetime.now() + datetime.timedelta(days=REMEMBER_DAYS)
                        if remember:
                            token = issue_remember_token(email)
                            cm.set(REMEMBER_COOKIE, token, expires_at=expires, key="set_remember")
                            cm.set("plan_agent_email", email, expires_at=expires, key="set_email")
                        else:
                            cm.delete(REMEMBER_COOKIE, key="del_remember")
                            cm.delete("plan_agent_email", key="del_email")
                except Exception as _ce:
                    _log.warning(f"로그인 저장 쿠키 처리 실패(무시): {_ce}")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def _render_register_form():
    st.subheader("📝 회원가입 요청")
    st.caption("회원가입 후 관리자 승인을 받아야 시스템을 사용할 수 있습니다.")
    with st.form("register_form", clear_on_submit=True):
        email = st.text_input("이메일", key="reg_email").strip().lower()
        password = st.text_input("비밀번호 (8자 이상)", type="password", key="reg_pw")
        password2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
        submitted = st.form_submit_button("회원가입 요청 보내기", use_container_width=True)
        if submitted:
            if password != password2:
                st.error("비밀번호 확인이 일치하지 않습니다.")
                return
            ok, msg = register_user(email, password)
            (st.success if ok else st.error)(msg)


def _render_admin_initial_password_form():
    """관리자(orion0321) 계정에 비밀번호가 아직 없을 때만 동작."""
    admin = get_user(ADMIN_EMAIL)
    needs_init = bool(admin) and not admin.get("password_hash")
    st.subheader("🛠 관리자 초기 비밀번호 설정")
    st.caption(f"관리자 계정({ADMIN_EMAIL})의 초기 비밀번호를 한 번만 직접 설정합니다.")
    if not needs_init:
        st.info("관리자 비밀번호가 이미 설정되어 있습니다. 일반 로그인 탭을 사용하세요.")
        return
    with st.form("admin_init_form", clear_on_submit=True):
        password = st.text_input("새 비밀번호 (8자 이상)", type="password", key="admin_init_pw")
        password2 = st.text_input("비밀번호 확인", type="password", key="admin_init_pw2")
        submitted = st.form_submit_button("관리자 비밀번호 설정", use_container_width=True, type="primary")
        if submitted:
            if password != password2:
                st.error("비밀번호 확인이 일치하지 않습니다.")
                return
            if not password or len(password) < 8:
                st.error("비밀번호는 8자 이상이어야 합니다.")
                return
            _set_password_for(ADMIN_EMAIL, password)
            st.success("관리자 비밀번호가 설정되었습니다. 이제 로그인 탭에서 로그인하세요.")


def render_login_page():
    """로그인 안 된 상태에서 보여 줄 전체 페이지."""
    try:
        from ui_theme import inject_global_css
        inject_global_css()
    except Exception:
        pass
    st.markdown(
        """
        <div class="appx-login-hero">
            <h1>🔒 제안서 & 추진계획서 자동 생성 Agent</h1>
            <p>관리자 승인을 받은 계정으로 로그인해 5단계 마법사를 시작하세요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 관리자 계정에 비밀번호가 아직 설정되지 않은 최초 1회만 인라인 초기화 UI 노출
    try:
        admin = get_user(ADMIN_EMAIL)
        if admin and not admin.get("password_hash"):
            with st.expander(f"🛠 [관리자 전용] 최초 1회 비밀번호 설정 ({ADMIN_EMAIL})", expanded=True):
                _render_admin_initial_password_form()
    except Exception:
        pass

    tab1, tab2 = st.tabs(["로그인", "회원가입 요청"])
    with tab1:
        _render_login_form()
    with tab2:
        _render_register_form()


def _try_cookie_autologin():
    """세션에 로그인 정보가 없을 때 쿠키의 자동 로그인 토큰으로 복원을 시도한다."""
    if current_user() or not _HAS_COOKIES:
        return
    try:
        cm = get_cookie_manager()
        if not cm:
            return
        token = cm.get(REMEMBER_COOKIE)
        if not token:
            return
        email = consume_remember_token(token)
        if not email:
            return
        fresh = get_user(email)
        if fresh and fresh.get("status") == "approved":
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = _connect()
            c = conn.cursor()
            c.execute("UPDATE users SET last_login_at = ? WHERE email = ? COLLATE NOCASE", (now, email))
            conn.commit()
            conn.close()
            fresh["last_login_at"] = now
            st.session_state.auth_user = fresh
            st.session_state.auth_login_time = datetime.datetime.now().isoformat()
            _log.info(f"자동 로그인(쿠키) 성공: {email}")
    except Exception as _e:
        _log.warning(f"자동 로그인 시도 실패(무시): {_e}")


def require_login():
    """모든 페이지 진입 전에 호출. 미로그인 시 로그인 화면을 그리고 st.stop() 한다."""
    ensure_users_table()
    seed_admin()
    build_cookie_manager()   # 실행당 1회: 최신 쿠키 로드
    _try_cookie_autologin()
    user = current_user()
    if not user:
        render_login_page()
        st.stop()
    # status 변경 즉시 반영
    fresh = get_user(user["email"])
    if not fresh or fresh["status"] != "approved":
        logout()
        st.error("계정 상태가 변경되었습니다. 다시 로그인해주세요.")
        render_login_page()
        st.stop()
    st.session_state.auth_user = fresh
    return fresh


def render_sidebar_user_panel(extra_panel=None):
    """사이드바에 현재 로그인 정보 + 로그아웃 버튼을 그린다.
    extra_panel: 선택적 콜백. 계정 카드와 푸터 사이에 추가 패널(예: 단계 진행 상황)을 렌더한다."""
    user = current_user()
    if not user:
        return
    email = str(user.get("email", ""))
    role = str(user.get("role", "user"))
    initial = (email[:1] or "U").upper()
    is_adm = role == "admin"
    role_cls = "appx-role-admin" if is_adm else "appx-role-user"
    role_label = "👑 ADMIN" if is_adm else "USER"
    avatar_cls = "appx-avatar appx-avatar-admin" if is_adm else "appx-avatar"
    last_login = str(user.get("last_login_at") or "").strip()
    with st.sidebar:
        # 브랜드 (로고 칩 + 타이틀 + 서브)
        st.markdown(
            '<div class="appx-brand">'
            '<div class="appx-brand-logo">🤖</div>'
            '<div><div class="appx-brand-title">제안서 Agent</div>'
            '<div class="appx-brand-sub">AI Proposal Suite</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("### 계정")
        st.markdown(
            f'<div class="appx-usercard">'
            f'<div class="{avatar_cls}">{initial}</div>'
            f'<div class="appx-user-meta">'
            f'<div class="appx-user-email" title="{email}">{email}</div>'
            f'<span class="appx-role-badge {role_cls}">{role_label}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        if last_login:
            st.markdown(f'<div class="appx-lastlogin">최근 로그인 · {last_login}</div>', unsafe_allow_html=True)
        if st.button("🚪 로그아웃", use_container_width=True, key="sidebar_logout"):
            logout()
            st.rerun()
        # 호출자가 넘긴 추가 패널(예: 메인 앱의 단계 진행 상황)을 계정 카드 아래에 렌더
        if extra_panel is not None:
            try:
                extra_panel()
            except Exception as _ep:
                _log.warning(f"사이드바 추가 패널 렌더 실패(무시): {_ep}")
        if is_admin():
            st.markdown("### 관리")
            render_admin_panel_sidebar()
        # 푸터 (가동 상태 + 버전)
        st.markdown(
            '<div class="appx-sidebar-footer">'
            '<span class="appx-foot-dot"></span> 온라인'
            '<span class="appx-foot-ver">v5.1 · 2026</span>'
            '</div>',
            unsafe_allow_html=True,
        )


def render_admin_panel_sidebar():
    """관리자에게만 표시되는 승인 패널."""
    with st.sidebar.expander("🛡 관리자 패널 — 가입 요청 관리", expanded=True):
        pending = list_users("pending")
        if not pending:
            st.caption("대기 중인 가입 요청이 없습니다.")
        else:
            st.caption(f"대기 중: **{len(pending)}건**")
            for u in pending:
                with st.container(border=True):
                    st.write(f"**{u['email']}**")
                    st.caption(f"신청일 {u['created_at']}")
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("승인", key=f"approve_{u['id']}", use_container_width=True, type="primary"):
                            if approve_user(u["email"], current_user()["email"]):
                                st.success(f"{u['email']} 승인됨")
                                st.rerun()
                    with bc2:
                        if st.button("거절", key=f"reject_{u['id']}", use_container_width=True):
                            if reject_user(u["email"], current_user()["email"]):
                                st.warning(f"{u['email']} 거절됨")
                                st.rerun()

        all_users = list_users()
        with st.expander(f"전체 사용자 ({len(all_users)})", expanded=False):
            for u in all_users:
                st.caption(f"- {u['email']} · {u['role']} · {u['status']}")
                if u["role"] != "admin" and u["status"] != "pending":
                    if st.button("계정 삭제", key=f"del_{u['id']}"):
                        delete_user(u["email"])
                        st.rerun()
