# ============================================================
#  plan_cf_ensure.ps1
#  plan 터널(cloudflared-plan) ingress에 plan.assisai.net 보장.
#  - 이미 있으면 아무것도 안 함(멱등).
#  - 없으면 plan.songstock.art 규칙 바로 뒤에 추가하고 백업 후 서비스 재시작.
#  ※ ProgramData\cloudflared 수정 + 서비스 재시작은 관리자 권한 필요.
#    plan_start.bat 가 관리자 권한으로 self-elevate 한 뒤 호출한다.
# ============================================================
$ErrorActionPreference = 'Stop'
$cfg = 'C:\ProgramData\cloudflared\cloudflared-plan\config.yml'
$svc = 'cloudflared-plan'
$host2 = 'plan.assisai.net'

if (-not (Test-Path $cfg)) {
    Write-Host "  [X] cloudflared-plan config 없음: $cfg"
    exit 1
}

$raw = Get-Content $cfg -Raw

if ($raw -match [regex]::Escape($host2)) {
    Write-Host "  [v] ingress 이미 $host2 포함 (변경 없음)"
    exit 0
}

# plan.songstock.art 규칙 블록을 찾아 그 뒤에 plan.assisai.net 규칙을 삽입
$pat = '(-\s*hostname:\s*plan\.songstock\.art\s*\r?\n\s*service:\s*http://localhost:8501)'
$add = "`r`n  - hostname: $host2`r`n    service: http://localhost:8501"

if ($raw -match $pat) {
    $new = [regex]::Replace($raw, $pat, { param($m) $m.Groups[1].Value + $add })
} else {
    # 폴백: catch-all(http_status:404) 앞에 삽입
    $block = "  - hostname: $host2`r`n    service: http://localhost:8501`r`n"
    $new = [regex]::Replace($raw, '(?m)^(\s*-\s*service:\s*http_status:404\s*)$', ($block + '$1'))
}

if ($new -eq $raw) {
    Write-Host "  [!] ingress 자동 삽입 실패 - config 수동 확인 필요: $cfg"
    exit 1
}

# 백업 후 UTF-8(BOM 없음)으로 저장
Copy-Item $cfg "$cfg.bak" -Force
[System.IO.File]::WriteAllText($cfg, $new, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "  [v] ingress에 $host2 추가 완료 (백업: config.yml.bak)"

# 서비스 재시작(변경 반영)
try {
    Restart-Service $svc -Force -ErrorAction Stop
    Write-Host "  [v] $svc 재시작 완료"
} catch {
    & sc.exe stop $svc | Out-Null
    Start-Sleep -Seconds 2
    & sc.exe start $svc | Out-Null
    Write-Host "  [v] $svc 재기동(sc) 완료"
}
Start-Sleep -Seconds 3
exit 0
