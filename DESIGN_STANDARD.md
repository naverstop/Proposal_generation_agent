# plan_agent — UI/UX 디자인 표준 (Design Standard)

> 버전 1.0 · 2026-06-08 · 적용 범위: 전 화면(로그인 / 메인 5단계 마법사 / History 대시보드)
>
> 목적: 화면마다 제각각이던 제목·간격·색·컴포넌트 사용을 **단일 규칙**으로 통일한다.
> 모든 디자인 토큰과 표준 컴포넌트는 `ui_theme.py` 한 곳에서만 정의/수정한다.

---

## 0. 대원칙

1. **토큰 단일 출처**: 색·간격·반경·그림자는 `ui_theme.py`의 `:root` CSS 변수(`--appx-*`)만 사용한다. 화면에 raw HEX(`#2563EB` 등)를 직접 박지 않는다.
2. **컴포넌트 헬퍼 우선**: 제목/배지/스테퍼 등은 Streamlit 기본 위젯을 임의로 쓰지 말고 `ui_theme.py`의 헬퍼를 쓴다.
3. **프로세스 불간섭**: 생성·재시도·진행률 등 **로직은 표준화 대상이 아니다.** 표준화는 표현 계층(제목·간격·레이아웃)에 한정한다.
4. **다크모드 자동 대응**: 색은 항상 토큰을 통해 쓰므로 `prefers-color-scheme: dark`에서 자동 전환된다.

---

## 1. 컬러 토큰

| 용도 | 토큰 | 라이트 값 |
|---|---|---|
| 배경 | `--appx-bg` | `#F8FAFC` |
| 표면(카드) | `--appx-surface` | `#FFFFFF` |
| 보조 표면 | `--appx-surface-2` | `#F1F5F9` |
| 테두리 | `--appx-border` / `--appx-border-strong` | `#E2E8F0` / `#CBD5E1` |
| 본문 텍스트 | `--appx-text` | `#0F172A` |
| 보조 텍스트 | `--appx-text-muted` | `#64748B` |
| 주색(Primary) | `--appx-primary` / `-hover` / `-soft` | `#2563EB` / `#1D4ED8` / `#DBEAFE` |
| 성공 | `--appx-success` / `-soft` | `#10B981` |
| 경고 | `--appx-warning` / `-soft` | `#F59E0B` |
| 위험 | `--appx-danger` / `-soft` | `#EF4444` |
| 정보 | `--appx-info` / `-soft` | `#0EA5E9` |

**색 사용 규칙**
- 주요 행동(제출/생성 시작) 버튼 = Primary. 보조/취소 = 기본 표면 버튼.
- 상태 의미색은 의미에 맞게만: 성공=완료, 경고=주의/대기, 위험=오류/삭제, 정보=안내.
- 포인트(강조) 영역은 `-soft` 배경 + 동색 좌측 4px 보더(예: 산출물 다운로드 패널).

> ⚠️ 테마에 없는 변수(`--appx-bg-soft` 등)는 쓰지 않는다. 보조 배경은 `--appx-surface-2`.

---

## 2. 간격 · 반경 · 그림자

- 반경: 작음 `--appx-radius-sm`(6) / 기본 `--appx-radius-md`(10) / 큼 `--appx-radius-lg`(14).
- 그림자: 카드/버튼 `--appx-shadow-sm`, 떠 있는 요소 `--appx-shadow-md`.
- 콘텐츠 최대 폭: 1180px(`.main .block-container`). 단계 본문은 이 폭 안에서 배치.
- 세로 리듬: 섹션 간 ≈ 14px, 하위 섹션 위 18px / 아래 8px(헬퍼가 자동 처리).

---

## 3. 타이포그래피

- 폰트: **Pretendard** (폴백: system-ui / Malgun Gothic). `ui_theme.py`에서 전역 주입.
- 위계(상→하):
  1. **페이지 헤더** `page_header()` — 화면 최상단 1회. 1.7rem/800.
  2. **섹션 헤더** `section_header()` — 각 단계 본문 최상단. 1.25rem/800 + 좌측 4px 액센트.
  3. **하위 제목** `sub_section()` — 섹션 내부 단계. 1.02rem/700 + 번호 칩.
  4. 본문 `st.write/markdown`, 보조설명 `st.caption`.

---

## 4. 표준 컴포넌트 헬퍼 (`ui_theme.py`)

| 헬퍼 | 용도 | 대체 대상(금지) |
|---|---|---|
| `page_header(title, subtitle, meta)` | 화면 최상단 헤더 | `st.title` |
| `section_header(title, desc="", icon="")` | 단계 본문 최상단 제목 | `st.header("...")` |
| `sub_section(title, num=None, desc="")` | 섹션 내부 하위 제목 | `st.subheader`, `st.markdown("### / #### / #####")` |
| `render_stepper(labels, current_index, completed)` | 5단계 진행 스테퍼 | 직접 HTML |
| `status_badge(label, kind)` | 상태 배지(HTML 문자열) | 인라인 span |

**사용 예**
```python
from ui_theme import section_header, sub_section
section_header("제안서 자동 생성", desc="확정된 주제·목차로 본문을 생성합니다.", icon="🛠")
sub_section("초안 검토 및 수정", num=1)
```

**제목 표기 규칙**
- 단계 본문 제목은 `section_header`로 통일하고, 이모지는 `icon=` 인자로 분리(텍스트에 섞지 않는다).
- 하위 단계 번호는 `sub_section(num=1)`처럼 칩으로 표기(텍스트 `"1. ..."` 금지).

---

## 5. 컨트롤(버튼/입력/알림) 규칙

- **버튼 폭**: 단계의 주요 액션은 `use_container_width=True`. 모바일에서 자동 100%.
- **버튼 종류**: 주요 액션 `type="primary"` 1개 원칙(한 화면에 Primary 남발 금지).
- **위험 액션**(삭제/초기화): 라벨에 아이콘(🗑) + 기본/secondary 버튼. 결과는 `st.warning`/`st.success`로 피드백.
- **입력**: `label`은 항상 제공하되 시각적 중복이면 `label_visibility="collapsed"`. placeholder로 예시 제공.
- **알림 사용처**: `st.info`=안내, `st.success`=완료, `st.warning`=주의/대기, `st.error`=차단/실패. 진행 상황은 `st.status`/`st.progress`.

---

## 6. 레이아웃 패턴

- **단계 화면 골격**: `section_header` → (전제조건 가드 `st.warning`+`st.stop`) → 설정 입력 → 실행 버튼 → 결과.
- **표/목록**: 동일 컬럼 비율을 헤더와 행에서 공유. 게시판형은 `st.columns`로 ID/제목/일자/작업 4열을 유지.
- **강조 패널**(다운로드 등): `-soft` 배경 + 좌측 4px 보더 박스.
- **인라인 `<style>` 금지 원칙**: 화면 파일에 새 CSS를 넣지 말고 `ui_theme.py`에 클래스를 추가해 재사용한다.

---

## 6-1. 사이드바 (전 페이지 공통)

`render_sidebar_user_panel()`(auth.py) + 사이드바 CSS(ui_theme.py)로 통일.
- **브랜드**: 로고 칩(`🤖`, primary→violet 그라데이션) + `제안서 Agent` + 서브 `AI Proposal Suite`.
- **네비게이션**: 멀티페이지 링크에 아이콘(`📝`/`🗂️`)·호버·활성 좌측 액센트바.
- **프로필 카드**: 아바타(이메일 첫 글자, 링) + 이메일 + 역할 배지 + 최근 로그인.
- **역할 배지**: `user`=블루(info), `admin`=골드 그라데이션(`👑 ADMIN`) + 아바타 글로우로 **강조**.
- **푸터**: 가동 상태 점(green pulse) + 버전(`v5.1 · 2026`).
- 사이드바 신규 요소도 색은 토큰만 사용 → 라이트/다크 자동 대응.

## 7. 인증/로그인 화면

- 로그인 히어로(`.appx-login-hero`) + 탭(로그인 / 회원가입 요청).
- **로그인 저장**: 로그인 폼의 "로그인 저장" 체크 시 30일 자동 로그인(쿠키 토큰). 토큰은 해시만 DB(`auth_tokens`)에 저장, 평문은 쿠키에만 보관. 로그아웃 시 토큰·쿠키 폐기.

---

## 8. 반응형

- 768px 이하: 헤더 세로 정렬, 5단계 탭 가로 스크롤, 버튼 100% 폭, 스테퍼 라벨 축약(현재/오류만 표시).
- 480px 이하: 제목·탭 폰트 추가 축소.
- 새 컴포넌트 추가 시 위 브레이크포인트에서 깨지지 않는지 확인.

---

## 9. 변경 절차

1. 색/간격/컴포넌트가 필요하면 **먼저 `ui_theme.py`에 토큰/헬퍼/클래스를 추가**한다.
2. 화면 파일에서는 그 헬퍼/클래스를 호출만 한다.
3. 본 문서의 표를 함께 갱신한다.
