# plan_agent — 운영정보

> 최종 점검: 2026-06-04 · 서버: SONGS_SERVER

| 항목 | 값 |
|---|---|
| 역할 | 제안서 생성 (Proposal Generator) |
| 스택 | Python 3.11.9 + venv / **Streamlit** |
| 홈 | `D:\plan_agent` |
| 시작 배치 | `D:\plan_agent\plan_start.bat` (관리자 자동상승 · plan 한정 종료 · ingress 보장) |
| 종료 배치 | `D:\plan_agent\plan_stop.bat` (plan 한정 종료 + 터널 중지) |
| 진입점 | `streamlit run 0_Proposal_Generator.py --server.port 8501` |
| 웹/포트 | Streamlit **:8501** |
| 외부 도메인 | https://plan.songstock.art , https://plan.assisai.net |
| Cloudflare | 서비스 `cloudflared-plan` / 터널 `plan-tunnel` (`40d2329d-…`) → 두 호스트 모두 :8501 |
| CF ingress 헬퍼 | `plan_cf_ensure.ps1` (plan.assisai.net ingress 멱등 주입+재시작) |
| GPU | GPU1 (RTX 3050) = `CUDA_VISIBLE_DEVICES=1` |

## DB
| 엔진 | **SQLite** |
|---|---|
| 파일 | `D:\plan_agent\history.db` |
| 서비스 | 없음 (파일 기반) |

## 환경변수 (plan_start.bat)
- `CUDA_VISIBLE_DEVICES=1`
- `PLAN_HOME=D:\plan_agent`
- `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` / `PYTHONUNBUFFERED=1`

## 경로/파일
- `.env`: `D:\plan_agent\.env`
- venv: `D:\plan_agent\.venv` (`requirements.txt`)
- 로그: `D:\plan_agent\logs`

## 백업
- DB: `F:\backup\db\plan\YYYYMMDD\history.db` (SQLite 파일 복사, 매일 04:00)
- 설정: `F:\backup\config\plan\`

## 스모크 점검
```powershell
cd D:\plan_agent; .\plan_start.bat
# 브라우저 http://localhost:8501 접속 확인
```
