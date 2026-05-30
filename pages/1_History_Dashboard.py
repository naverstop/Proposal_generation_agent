# pages/1_History_Dashboard.py
import sys
import os
# 상위 폴더(루트)의 auth 모듈을 import 할 수 있도록 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import sqlite3
import pandas as pd
import json
from docx import Document
import io

from auth import require_login, render_sidebar_user_panel
from logging_setup import get_logger

_log = get_logger("HISTORY")

st.set_page_config(page_title="생성 기록 대시보드", layout="wide")
# --- 인증 가드 ---
_user = require_login()
if st.session_state.get("_history_logged_user") != _user["email"]:
    _log.info(f"History 페이지 진입: {_user['email']}")
    st.session_state._history_logged_user = _user["email"]
render_sidebar_user_panel()

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "history.db")

def load_projects_from_db(search_query=""):
    """데이터베이스에서 모든 프로젝트 목록을 검색어에 따라 불러옵니다."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if search_query:
        c.execute("SELECT id, topic, timestamp FROM projects WHERE topic LIKE ? ORDER BY timestamp DESC", ('%' + search_query + '%',))
    else:
        c.execute("SELECT id, topic, timestamp FROM projects ORDER BY timestamp DESC")
    projects = [dict(row) for row in c.fetchall()]
    conn.close()
    return projects

def delete_project_from_db(project_id):
    """특정 프로젝트와 관련된 모든 데이터를 DB에서 삭제합니다."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    c.execute("DELETE FROM project_stages WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()


def load_stages_from_db(project_id):
    """특정 프로젝트의 모든 단계별 결과를 불러옵니다."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT stage_name, content, llm_type FROM project_stages WHERE project_id = ? ORDER BY id ASC", (project_id,))
    stages = [dict(row) for row in c.fetchall()]
    conn.close()
    return stages

def create_docx_from_db(content):
    """텍스트 콘텐츠로 DOCX 파일을 생성합니다."""
    document = Document()
    for line in content.split('\n'):
        if line.startswith('### '):
            document.add_heading(line.lstrip('# ').strip(), level=3)
        elif line.startswith('## '):
            document.add_heading(line.lstrip('# ').strip(), level=2)
        elif line.startswith('# '):
            document.add_heading(line.lstrip('# ').strip(), level=1)
        elif line.strip():
            document.add_paragraph(line.strip())
    bio = io.BytesIO()
    document.save(bio)
    return bio.getvalue()

st.markdown("""
<style>
    .stApp {
        background-color: #F0F8FF;
    }
    .stButton>button {
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        color: #334155;
        font-weight: 600;
    }
    .stButton>button:hover {
        border-color: #2563EB;
        color: #2563EB;
    }
    .stButton>button[kind="primary"] {
        background-color: #2563EB;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

st.title("🗂️ 생성 기록 대시보드")
st.info("이곳에서 과거에 생성했던 모든 제안서 프로젝트의 기록을 확인하고 관리할 수 있습니다.")

search_query = st.text_input("주제 검색:", placeholder="검색할 제안서 주제를 입력하세요...")

projects = load_projects_from_db(search_query)

if not projects:
    st.warning("아직 생성된 프로젝트 기록이 없거나, 검색 결과가 없습니다.")
else:
    col1, col2, col3, col4 = st.columns([1, 4, 2, 3])
    col1.write("**번호**")
    col2.write("**제안서 주제**")
    col3.write("**생성일자**")
    col4.write("**작업**")
    st.markdown("---")

    for project in projects:
        col1, col2, col3, col4 = st.columns([1, 4, 2, 3])
        with col1:
            st.write(project['id'])
        with col2:
            st.write(project['topic'])
        with col3:
            st.write(project['timestamp'])
        with col4:
            b_col1, b_col2 = st.columns(2)
            with b_col1:
                if st.button("상세 보기", key=f"view_{project['id']}", use_container_width=True):
                    if st.session_state.get("selected_project_id_for_view") == project['id']:
                        del st.session_state.selected_project_id_for_view
                    else:
                        st.session_state.selected_project_id_for_view = project['id']
                    st.rerun()
            with b_col2:
                if st.button("삭제", key=f"delete_{project['id']}", use_container_width=True, type="secondary"):
                    delete_project_from_db(project['id'])
                    st.success(f"프로젝트 #{project['id']}가 삭제되었습니다.")
                    st.rerun()
        
        if st.session_state.get("selected_project_id_for_view") == project['id']:
            with st.expander(f"프로젝트 #{project['id']} 상세 내용", expanded=True):
                stages = load_stages_from_db(project['id'])
                if not stages:
                    st.info("이 프로젝트의 단계별 기록이 없습니다.")
                else:
                    stage_dict = {s['stage_name']: s for s in stages}
                    tab_names = [s.split(': ')[1] for s in stage_dict.keys() if ':' in s]
                    stage_tabs = st.tabs(tab_names)
                    
                    tab_idx = 0
                    for stage_name, stage in stage_dict.items():
                        if ':' not in stage_name: continue

                        with stage_tabs[tab_idx]:
                            st.subheader(f"'{stage['stage_name']}' 결과")
                            if stage['llm_type']:
                                st.caption(f"사용된 LLM: {stage['llm_type']}")
                            
                            content = stage['content']
                            try:
                                parsed_json = json.loads(content)
                                st.json(parsed_json)
                            except (json.JSONDecodeError, TypeError):
                                st.text_area("내용", content, height=300, key=f"stage_{project['id']}_{tab_idx}")

                            if stage['stage_name'] == "3단계: 본문 생성":
                                st.markdown("---")
                                
                                button_cols = st.columns(4) 
                                button_idx = 0

                                button_cols[button_idx].download_button(
                                    label="📥 초안 DOCX 다운로드",
                                    data=create_docx_from_db(content),
                                    file_name=f"[{project['timestamp'].split(' ')[0]}] {project['topic']}_초안.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"docx_down_{project['id']}",
                                    use_container_width=True
                                )
                                button_idx += 1
                                
                                if "3단계: 출처 목록" in stage_dict:
                                    button_cols[button_idx].download_button(
                                        label="📥 출처(.txt) 다운로드",
                                        data=stage_dict["3단계: 출처 목록"]['content'].encode('utf-8'),
                                        file_name=f"[{project['timestamp'].split(' ')[0]}] {project['topic']}_citations.txt",
                                        mime="text/plain",
                                        key=f"cite_down_{project['id']}",
                                        use_container_width=True
                                    )
                                    button_idx += 1

                                if button_cols[button_idx].button("🧐 품질 검증하기", key=f"review_nav_{project['id']}", use_container_width=True):
                                    st.session_state.selected_project_id = project['id']
                                    st.session_state.active_tab = "4단계: 최종 품질 검증"
                                    st.switch_page("0_Proposal_Generator.py")
                                button_idx += 1
                            
                            if stage['stage_name'] == "4단계: 최종본":
                                st.markdown("---")
                                b_col1, b_col2 = st.columns(2)
                                with b_col1:
                                    st.download_button(
                                        label="📥 최종본 DOCX 다운로드",
                                        data=create_docx_from_db(content),
                                        file_name=f"[{project['timestamp'].split(' ')[0]}] {project['topic']}_최종본.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key=f"final_docx_down_{project['id']}",
                                        use_container_width=True
                                    )
                                with b_col2:
                                    if st.button("📝 PPT 전환하기", key=f"ppt_nav_{project['id']}", use_container_width=True):
                                        st.session_state.selected_project_id = project['id']
                                        st.session_state.active_tab = "5단계: PPT 전환"
                                        st.switch_page("0_Proposal_Generator.py")

                        tab_idx += 1