@echo off
REM ============================================================
REM  Plan Agent STOP — plan Streamlit(:8501) + Cloudflare 터널 깔끔 종료
REM  ※ plan 전용(포트 %PLAN_PORT% + %PLAN_HOME% 경로)만 종료 → 타 프로젝트 보호
REM  ※ saju_stop.bat 표준 준수(포트가 빌 때까지 반복 종료)
REM ============================================================
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ── 관리자 권한 자동 상승 (다른 세션/권한의 프로세스까지 확실히 종료) ──
net session >nul 2>&1
if errorlevel 1 (
    echo [관리자 권한으로 다시 실행합니다...]
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "PLAN_HOME=D:\plan_agent"
set "PLAN_PORT=8501"
set "CF_SERVICE=cloudflared-plan"

echo ============================================================
echo    Plan Agent STOP
echo ============================================================
echo.

REM ------------------------------------------------------------
REM  [1/2] plan Streamlit(:%PLAN_PORT%) 종료 — plan 한정(타 프로젝트 보호)
REM        (1) plan 전용 포트 점유 프로세스
REM        (2) CommandLine 에 0_Proposal_Generator + %PLAN_HOME% 경로가 모두 포함된 python.exe
REM        포트가 빌 때까지 최대 10회 트리 종료(/T). 자기 자신은 제외.
REM ------------------------------------------------------------
echo [1/2] plan Streamlit(:%PLAN_PORT%) 종료 중...
powershell -NoProfile -Command "$port=%PLAN_PORT%; $proj='%PLAN_HOME%'; for($try=1;$try -le 10;$try++){ $ids=@(); Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue | ForEach-Object { $ids += $_.OwningProcess }; Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*0_Proposal_Generator*' -and $_.CommandLine -like ('*'+$proj+'*') } | ForEach-Object { $ids += $_.ProcessId }; $ids = $ids | Where-Object { $_ -and $_ -ne $PID -and $_ -ne 0 } | Sort-Object -Unique; if(-not $ids){ break }; foreach($pp in $ids){ Write-Host ('  - plan PID '+$pp+' 트리 종료(/T) [try '+$try+']'); taskkill /F /T /PID $pp 2>$null | Out-Null }; Start-Sleep -Milliseconds 700 }; if(Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue){ Write-Host '  [X] :%PLAN_PORT% 점유 잔존 — 고아 소켓일 수 있음(작업관리자 수동 종료 또는 재부팅 필요)' } else { Write-Host '  [v] Streamlit 종료 완료 (포트 clear)' }"

REM ------------------------------------------------------------
REM  [2/2] Cloudflare 터널(plan 전용 서비스) 중지
REM ------------------------------------------------------------
echo [2/2] Cloudflare 터널(%CF_SERVICE%) 중지 중...
sc query %CF_SERVICE% >nul 2>&1
if errorlevel 1 (
    echo   [-] %CF_SERVICE% 서비스 없음 (건너뜀)
) else (
    sc stop %CF_SERVICE% >nul 2>&1
    echo   [v] %CF_SERVICE% 중지 요청 완료
)

echo.
echo ============================================================
echo   [완료] plan Streamlit / 터널 종료
echo   (다른 에이전트 saju/assis/unse 등은 영향 없음)
echo ============================================================
endlocal
pause
