@echo off
echo ===================================================
echo  AI Proposal Project Launcher (Stable CTranslate2 Version)
echo ===================================================
echo.
echo [INFO] This script will start both the Frontend and the
echo        CTranslate2 Backend Server for testing 'My Own LLM'.
echo.

REM Agent 프로젝트 폴더 경로
set AGENT_PATH="C:\agent_project"

REM LLM 프로젝트 폴더 경로
set LLM_PATH="C:\LLM_project"

echo [1/2] Starting LLM Backend Server (CTranslate2)...
cd /d %LLM_PATH%
start "LLM Server (CTranslate2)" cmd /k "call .\.venv\Scripts\activate && uvicorn api:app --reload --host 0.0.0.0 --port 8000"

echo.
echo Waiting 8 seconds for LLM server to initialize...
timeout /t 8 /nobreak > nul

echo.
echo [2/2] Starting Agent Frontend Application...
cd /d %AGENT_PATH%
start "Agent Frontend" cmd /k "call .\.venv\Scripts\activate && streamlit run 0_Proposal_Generator.py"

echo.
echo All projects launched successfully in new windows.
pause
