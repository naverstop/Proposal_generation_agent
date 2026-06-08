@echo off
REM ============================================================
REM  plan_agent start (Streamlit) + Cloudflare Tunnel
REM  GPU1 / DB=SQLite (history.db) / Streamlit :8501
REM  도메인: https://plan.songstock.art , https://plan.assisai.net
REM         (둘 다 cloudflared-plan 서비스 / plan-tunnel 경유)
REM  ※ saju_start.bat 표준 준수:
REM     - 관리자 권한 자동 상승
REM     - plan 전용(포트 %PLAN_PORT% + %PLAN_HOME% 경로)만 종료 → 타 프로젝트 보호
REM     - 포트가 빌 때까지 반복 종료(/T)
REM ============================================================
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ── 관리자 권한 자동 상승 ──
REM   다른 세션/권한으로 떠 있는 기존 plan(:8501)·터널 서비스 제어에 관리자 권한 필요.
net session >nul 2>&1
if errorlevel 1 (
    echo [관리자 권한으로 다시 실행합니다...]
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "CUDA_VISIBLE_DEVICES=1"
set "PLAN_HOME=D:\plan_agent"
set "PLAN_PORT=8501"
set "PLAN_DOMAIN=plan.songstock.art"
set "PLAN_DOMAIN2=plan.assisai.net"
set "CF_SERVICE=cloudflared-plan"
set "CF_TUNNEL=plan-tunnel"
set "CF_EXE=C:\Program Files\WinGet\Links\cloudflared.exe"
set "CF_ENSURE=%PLAN_HOME%\plan_cf_ensure.ps1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

REM ── 개발+운영 겸용 토글 (향후 운영전용 전환 시 이 두 값만 변경) ──
REM   CONSOLE_MODE : show=콘솔 전면(로그 실시간 확인) / hide=최소화(백그라운드)
REM   DEV_RELOAD   : 1=소스 자동반영(runOnSave) / 0=고정(운영 전용)
set "CONSOLE_MODE=show"
set "DEV_RELOAD=1"
if /i "%CONSOLE_MODE%"=="hide" ( set "WINFLAG=/min" ) else ( set "WINFLAG=" )
if "%DEV_RELOAD%"=="1" ( set "RELOAD_ARGS=--server.runOnSave true" ) else ( set "RELOAD_ARGS=--server.runOnSave false" )

cd /d "%PLAN_HOME%"

if not exist "%PLAN_HOME%\.venv\Scripts\python.exe" (
    echo [X] venv missing: %PLAN_HOME%\.venv
    pause
    exit /b 1
)

echo ============================================================
echo    Plan Agent Startup
echo    https://%PLAN_DOMAIN%  /  https://%PLAN_DOMAIN2%
echo ============================================================
echo.

REM ════════════════════════════════════════════════════════════
REM  [1/4] 기존 plan 프로세스만 종료 (타 프로젝트 보호)
REM        (1) plan 전용 포트(%PLAN_PORT%) 점유 프로세스
REM        (2) CommandLine 에 0_Proposal_Generator + %PLAN_HOME% 경로가 모두 포함된 python.exe
REM        포트가 빌 때까지 최대 8회 트리 종료(/T). 자기 자신은 제외.
REM ════════════════════════════════════════════════════════════
echo [1/4] 기존 plan 프로세스만 종료 / 포트 정리 중... ^(경로 한정: %PLAN_HOME%^)
powershell -NoProfile -Command "$port=%PLAN_PORT%; $proj='%PLAN_HOME%'; for($try=1;$try -le 8;$try++){ $ids=@(); Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue | ForEach-Object { $ids += $_.OwningProcess }; Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*0_Proposal_Generator*' -and $_.CommandLine -like ('*'+$proj+'*') } | ForEach-Object { $ids += $_.ProcessId }; $ids = $ids | Where-Object { $_ -and $_ -ne $PID -and $_ -ne 0 } | Sort-Object -Unique; if(-not $ids){ break }; foreach($pp in $ids){ Write-Host ('  - plan PID '+$pp+' 트리 종료(/T) [try '+$try+']'); taskkill /F /T /PID $pp 2>$null | Out-Null }; Start-Sleep -Milliseconds 700 }; if(Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue){ Write-Host '  [X] 포트 점유 잔존! 작업관리자(관리자)에서 :%PLAN_PORT% python.exe 수동 종료 후 재실행' } else { Write-Host '  [v] 포트 clear - 재기동 준비' }"
if not exist "%PLAN_HOME%\logs" mkdir "%PLAN_HOME%\logs"

REM ════════════════════════════════════════════════════════════
REM  [2/4] Cloudflare 터널 점검 + ingress(plan.assisai.net) 보장
REM ════════════════════════════════════════════════════════════
echo.
echo [2/4] Cloudflare 터널 점검 / ingress 보장 중...
sc query %CF_SERVICE% >nul 2>&1
if errorlevel 1 (
    echo   [X] %CF_SERVICE% 서비스가 설치되지 않았습니다. cf 설정을 먼저 완료하세요.
) else (
    if exist "%CF_ENSURE%" (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%CF_ENSURE%"
    ) else (
        echo   [!] %CF_ENSURE% 없음 - ingress 자동 보장 건너뜀
    )
    for /f "tokens=3" %%S in ('sc query %CF_SERVICE% ^| findstr /i STATE') do set "CF_STATE=%%S"
    if /i not "!CF_STATE!"=="RUNNING" (
        echo   - %CF_SERVICE% 시작 중...
        sc start %CF_SERVICE% >nul 2>&1
    )
    echo   [v] Cloudflare 터널 서비스 실행 중 ^(%CF_SERVICE% / %CF_TUNNEL%^)
)

REM ════════════════════════════════════════════════════════════
REM  [3/4] Streamlit 기동
REM ════════════════════════════════════════════════════════════
echo.
echo [3/4] Streamlit :%PLAN_PORT% 기동 (CONSOLE_MODE=%CONSOLE_MODE% / DEV_RELOAD=%DEV_RELOAD%)...
start "plan-streamlit" %WINFLAG% "%PLAN_HOME%\.venv\Scripts\python.exe" -m streamlit run 0_Proposal_Generator.py --server.port %PLAN_PORT% --server.address 127.0.0.1 --server.headless true --server.enableCORS false --server.enableXsrfProtection false %RELOAD_ARGS%

set /a WAIT=0
:WAIT_LOCAL
powershell -NoProfile -Command "try{(Invoke-WebRequest http://127.0.0.1:%PLAN_PORT%/ -UseBasicParsing -TimeoutSec 3)|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto LOCAL_OK
set /a WAIT+=1
if %WAIT% GEQ 30 goto LOCAL_TIMEOUT
timeout /t 2 /nobreak >nul
goto WAIT_LOCAL
:LOCAL_TIMEOUT
echo   [!] 로컬 :%PLAN_PORT% 응답 지연 - 계속 진행
goto LOCAL_DONE
:LOCAL_OK
echo   [v] 로컬 Streamlit 응답 확인 (http://127.0.0.1:%PLAN_PORT%)
:LOCAL_DONE

REM ════════════════════════════════════════════════════════════
REM  [4/4] Cloudflare 외부 접속 검증 (두 도메인)
REM ════════════════════════════════════════════════════════════
echo.
echo [4/4] 외부 접속 검증 중... (%PLAN_DOMAIN% , %PLAN_DOMAIN2%)
call :VERIFY_EXT %PLAN_DOMAIN%
call :VERIFY_EXT %PLAN_DOMAIN2%

echo.
echo ============================================================
echo   [DONE] plan 기동 절차 완료
echo   외부 URL : https://%PLAN_DOMAIN%/  ,  https://%PLAN_DOMAIN2%/
echo   로컬     : http://127.0.0.1:%PLAN_PORT%
echo   터널     : %CF_TUNNEL% / 서비스 %CF_SERVICE%
echo   ※ plan.assisai.net 미연결 시: assisai.net 존에 CNAME(plan→
echo     40d2329d-c2b7-4815-8764-a85121b14db4.cfargotunnel.com) 필요
echo ============================================================
echo.
echo [plan] Streamlit은 별도 창("plan-streamlit")에서 실행 중입니다.
echo        이 창을 닫아도 서버는 유지됩니다. 종료하려면 plan_stop.bat 실행.
endlocal
pause > nul
goto :EOF

REM ------------------------------------------------------------
REM  :VERIFY_EXT <domain>  외부 https 접속을 최대 8회(3초 간격) 확인
REM ------------------------------------------------------------
:VERIFY_EXT
set "DOM=%~1"
set "EXT_OK=0"
set /a VWAIT=0
:VLOOP
for /f %%C in ('powershell -NoProfile -Command "try{(Invoke-WebRequest https://%DOM%/ -UseBasicParsing -TimeoutSec 15).StatusCode}catch{$_.Exception.Response.StatusCode.value__}"') do set "HTTP=%%C"
if "%HTTP%"=="200" set "EXT_OK=1"
if "%HTTP%"=="404" set "EXT_OK=1"
if "%HTTP%"=="401" set "EXT_OK=1"
if "%HTTP%"=="307" set "EXT_OK=1"
if "%EXT_OK%"=="1" (
    echo   [v] https://%DOM%/  ^(HTTP %HTTP%^)
    goto :EOF
)
set /a VWAIT+=1
if %VWAIT% GEQ 8 (
    echo   [!] https://%DOM%/  외부 접속 미확인 ^(마지막 응답: %HTTP%^)
    goto :EOF
)
timeout /t 3 /nobreak >nul
goto VLOOP
