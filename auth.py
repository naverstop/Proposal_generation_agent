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

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "orion0321@gmail.com").strip().lower()

PBKDF2_ITERATIONS = 260000
PBKDF2_ALGO = "sha256"


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
# 로그인 / 세션
# ---------------------------------------------------------------------------
def authenticate(email: str, password: str) -> tuple[bool, str, dict | None]:
    email = (email or "").strip().lower()
    user = get_user(email)
    if not user:
        return False, "등록되지 않은 이메일입니다.", None
    if user["status"] == "pending":
        return False, "관리자 승인 대기 중입니다. 관리자에게 문의하세요.", None
    if user["status"] == "rejected":
        return False, "가입이 거절되었습니다. 관리자에게 문의하세요.", None
    if not user["password_hash"]:
        # 관리자 초기 상태(비밀번호 미설정)인 경우 — 로그인 화면에서 별도 처리
        return False, "초기 비밀번호가 설정되지 않았습니다. '관리자 초기 비밀번호 설정' 탭을 사용하세요.", None
    if not _verify_password(email, password):
        return False, "비밀번호가 일치하지 않습니다.", None
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE users SET last_login_at = ? WHERE email = ? COLLATE NOCASE", (now, email))
    conn.commit()
    conn.close()
    user["last_login_at"] = now
    return True, "로그인 성공", user


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_admin() -> bool:
    u = current_user()
    return bool(u and u.get("role") == "admin")


def logout():
    for k in ("auth_user", "auth_login_time"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# UI 가드
# ---------------------------------------------------------------------------
def _render_login_form():
    st.subheader("🔐 로그인")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("이메일", key="login_email").strip().lower()
        password = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")
        if submitted:
            ok, msg, user = authenticate(email, password)
            if ok:
                st.session_state.auth_user = user
                st.session_state.auth_login_time = datetime.datetime.now().isoformat()
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
    st.title("🔒 로그인이 필요합니다")
    st.caption("이 시스템은 관리자가 승인한 계정만 사용할 수 있습니다.")
    tab1, tab2, tab3 = st.tabs(["로그인", "회원가입 요청", "관리자 초기 비밀번호"])
    with tab1:
        _render_login_form()
    with tab2:
        _render_register_form()
    with tab3:
        _render_admin_initial_password_form()


def require_login():
    """모든 페이지 진입 전에 호출. 미로그인 시 로그인 화면을 그리고 st.stop() 한다."""
    ensure_users_table()
    seed_admin()
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


def render_sidebar_user_panel():
    """사이드바에 현재 로그인 정보 + 로그아웃 버튼을 그린다."""
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown("### 👤 사용자")
        st.caption(f"{user['email']}  ·  `{user['role']}`")
        if st.button("로그아웃", use_container_width=True, key="sidebar_logout"):
            logout()
            st.rerun()
        if is_admin():
            render_admin_panel_sidebar()


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
