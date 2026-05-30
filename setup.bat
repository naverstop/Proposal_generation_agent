@echo off
chcp 65001 > nul
echo ============================================
echo  가상환경 설치 및 패키지 초기 세팅
echo ============================================
echo.

cd /d %~dp0

echo [1/2] .venv 가상환경 생성 중 (Python 3.11)...
uv venv .venv --python 3.11
if errorlevel 1 (
    echo [오류] venv 생성에 실패했습니다. uv가 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/2] requirements.txt 기반 패키지 설치 중...
uv pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  설치 완료! run.bat으로 앱을 실행하세요.
echo ============================================
pause
