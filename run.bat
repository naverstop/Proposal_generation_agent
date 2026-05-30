@echo off
chcp 65001 > nul
echo ============================================
echo  AI 제안서/PPT 자동 생성기 실행
echo ============================================
echo.

cd /d %~dp0

if not exist ".venv\Scripts\activate.bat" (
    echo [오류] .venv 환경이 없습니다. 먼저 setup.bat을 실행하세요.
    pause
    exit /b 1
)

echo [INFO] 가상환경 활성화 중...
call .venv\Scripts\activate.bat

echo [INFO] Streamlit 앱 시작 중...
streamlit run 0_Proposal_Generator.py

pause
