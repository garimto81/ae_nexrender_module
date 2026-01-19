---
name: work
description: Execute work instructions with parallel analysis, issue creation, and strict validation
---

# /work - 통합 작업 실행

작업 지시를 받아 **병렬 분석 → 이슈/문서 → Todo → E2E → TDD 보고**까지 자동 수행합니다.
`--loop` 모드에서는 **자율 판단 기반 반복 실행**을 지원합니다.

## 사용법

```bash
# 기본: 지시 기반 실행
/work <작업 지시 내용>
/work "API 성능 개선"

# 자동: 중간 확인 없이 실행
/work --auto "인증 시스템 리팩토링"

# 루프: 자율 판단 반복 실행 (기존 /auto)
/work --loop
/work --loop --max 5              # 최대 5개 작업
/work --loop resume [session_id]  # 세션 재개
/work --loop status               # 현재 상태
/work --loop pause                # 일시 정지
```

## 모드 비교

| 모드 | 입력 | 실행 방식 | Context 관리 |
|------|------|-----------|--------------|
| **기본** | 작업 지시 필수 | 5단계 워크플로우 | - |
| **--auto** | 작업 지시 필수 | 5단계 자동 실행 | - |
| **--loop** | 없음 (자율 판단) | 우선순위 기반 루프 | 90% 임계값 |

## 실행 흐름

```
/work 실행
    │
    ├─ Phase 1: 병렬 분석 ─────────────────────────────────┐
    │      │                                               │
    │      ├─ [Agent 1] 문서 분석 (PRD, CLAUDE.md, docs/)  │
    │      │      └─ 관련 문서 식별 및 요약                │
    │      │                                               │ 병렬
    │      └─ [Agent 2] 이슈 분석 (gh issue list)          │
    │             └─ 관련 이슈 식별 및 상태 확인           │
    │                                               ───────┘
    │
    ├─ Phase 2: 이슈 생성 + 문서 업데이트
    │      │
    │      ├─ 분석 결과 통합
    │      ├─ 새 이슈 생성 (필요 시)
    │      └─ 관련 문서 업데이트
    │
    ├─ Phase 3: Todo 작성
    │      │
    │      └─ TodoWrite로 작업 목록 생성
    │           ├─ 구현 태스크
    │           ├─ 테스트 태스크
    │           └─ 검증 태스크
    │
    ├─ Phase 4: E2E 엄격 검증
    │      │
    │      ├─ Playwright 테스트 실행
    │      ├─ 실패 시 자동 수정 (최대 2회)
    │      └─ 3회 실패 → /issue-failed
    │
    └─ Phase 5: TDD 검증 + 보고
           │
           ├─ 단위 테스트 실행
           ├─ 커버리지 확인
           └─ 최종 보고서 출력
```

## Phase 1: 병렬 분석

### 문서 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음을 분석하세요:
    1. CLAUDE.md - 관련 규칙/워크플로우
    2. tasks/prds/ - 관련 PRD
    3. docs/ - 관련 문서
    4. 영향받는 파일 목록

    JSON 형식으로 반환:
    {
        "related_docs": [...],
        "affected_files": [...],
        "recommendations": [...]
    }
    """,
    description="문서 분석"
)
```

### 이슈 분석 에이전트

```python
Task(
    subagent_type="Explore",
    prompt="""
    작업 지시: {instruction}

    다음을 분석하세요:
    1. gh issue list - 관련 이슈 검색
    2. gh pr list - 관련 PR 검색
    3. 중복 이슈 확인
    4. 의존성 이슈 파악

    JSON 형식으로 반환:
    {
        "related_issues": [...],
        "related_prs": [...],
        "duplicates": [...],
        "dependencies": [...]
    }
    """,
    description="이슈 분석"
)
```

## Phase 2: 이슈 생성 + 문서 업데이트

### 이슈 생성 기준

| 조건 | 동작 |
|------|------|
| 관련 이슈 없음 | 새 이슈 생성 |
| 관련 이슈 있음 (Open) | 기존 이슈에 코멘트 추가 |
| 관련 이슈 있음 (Closed) | 새 이슈 생성 + 참조 링크 |

### 문서 업데이트

```bash
# 자동 업데이트 대상
- tasks/prds/NNNN-prd-*.md  # PRD 생성/업데이트
- docs/*.md                  # 관련 문서 수정
- CHANGELOG.md               # 변경 로그 추가
```

## Phase 3: Todo 작성

### Todo 구조

```python
TodoWrite(todos=[
    {"content": "Phase 1: 문서/이슈 분석 완료", "status": "completed", "activeForm": "분석 중"},
    {"content": "Phase 2: 이슈 생성 및 문서 업데이트", "status": "completed", "activeForm": "업데이트 중"},
    {"content": "구현: <핵심 구현 항목>", "status": "in_progress", "activeForm": "구현 중"},
    {"content": "테스트: 단위 테스트 작성", "status": "pending", "activeForm": "테스트 작성 중"},
    {"content": "테스트: E2E 테스트 작성", "status": "pending", "activeForm": "E2E 작성 중"},
    {"content": "검증: TDD 검증", "status": "pending", "activeForm": "TDD 검증 중"},
    {"content": "보고: 최종 결과 보고", "status": "pending", "activeForm": "보고서 작성 중"}
])
```

## Phase 4: E2E 엄격 검증

### 검증 프로세스 (가설-검증 기반)

```
npx playwright test
    │
    ├─ 성공 → Phase 5 진행
    │
    └─ 실패 → /debug 자동 트리거 (가설-검증 사이클)
               │
               ├─ [D0] 이슈 등록 (자동)
               ├─ [D1] 원인 가설 작성 → 사용자 입력
               ├─ [D2] 검증 계획 설계 → 사용자 입력
               ├─ [D3] 가설 검증 실행 → 결과 입력
               │       │
               │       ├─ 확인 → [D4] 수정 허용 → 재검증
               │       │
               │       └─ 기각 → D1로 복귀 (최대 3회)
               │
               └─ 3회 가설 기각 → /issue failed
                                  └─ 수동 개입 요청
```

**변경점**: "자동 수정 시도 (최대 2회)" 삭제
→ 분석 없는 수정 시도 금지. 반드시 가설-검증 사이클 통과 필요

### 검증 기준

| 항목 | 기준 | 실패 시 |
|------|------|---------|
| E2E 테스트 | 100% 통과 | 자동 수정 |
| 성능 | 응답 시간 <3s | 경고 |
| 접근성 | a11y 오류 0 | 경고 |

## Phase 5: TDD 검증 + 보고

### TDD 검증

```bash
# 단위 테스트
pytest tests/ -v --cov=src --cov-report=term

# 커버리지 기준
- 신규 코드: 80% 이상
- 전체: 기존 대비 감소 불가
```

### 최종 보고서

```markdown
# 작업 완료 보고서

## 요약
- **작업 지시**: {instruction}
- **소요 시간**: XX분
- **생성 이슈**: #NNN
- **생성 PR**: #NNN

## Phase 1: 분석 결과
- 관련 문서: N개
- 관련 이슈: N개
- 영향 파일: N개

## Phase 2: 변경 사항
- 생성된 이슈: #NNN - {title}
- 업데이트된 문서: docs/XXX.md

## Phase 3: 구현 내역
| 파일 | 변경 | 설명 |
|------|------|------|
| src/xxx.py | +50/-10 | 기능 구현 |

## Phase 4: E2E 검증
- 테스트: NN개 통과
- 실패: 0개
- 성능: OK

## Phase 5: TDD 검증
- 단위 테스트: NN개 통과
- 커버리지: XX% (기준 80%)

## 다음 단계
1. PR 리뷰 요청
2. 배포 준비
```

## 예시

```bash
$ /work API 응답 캐싱 추가

🔍 Phase 1: 병렬 분석 중...
   [Agent 1] 문서 분석...
      - CLAUDE.md: 캐싱 관련 규칙 없음
      - docs/API.md: 캐싱 미언급
      - 영향 파일: src/api/*.py (5개)

   [Agent 2] 이슈 분석...
      - 관련 이슈: #45 (Closed), #67 (Open)
      - 중복: 없음

📝 Phase 2: 이슈 생성 + 문서 업데이트
   - 이슈 #67에 코멘트 추가
   - docs/API.md 캐싱 섹션 추가

✅ Phase 3: Todo 작성 완료 (7개 항목)

🧪 Phase 4: E2E 검증
   - playwright test: 15/15 통과

📊 Phase 5: TDD 검증
   - pytest: 42/42 통과
   - 커버리지: 85% (기준 80% 충족)

📋 최종 보고서 출력...
```

## 연동 커맨드

| 커맨드 | 연동 시점 |
|--------|----------|
| `/research plan` | Phase 1 전 (선택) |
| `/debug` | E2E 실패 시 (자동 트리거) |
| `/tdd` | Phase 5 |
| `/issue failed` | 3회 가설 기각 시 |
| `/commit` | 완료 후 |
| `/create pr` | 완료 후 |

## 연동 에이전트

| Phase | 에이전트 | 역할 |
|-------|----------|------|
| 1 | `Explore` x2 | 병렬 분석 |
| 2 | `general-purpose` | 이슈/문서 처리 |
| 4 | `test-engineer` | E2E 테스트 |
| 5 | `test-engineer` | TDD 검증 |

## 옵션

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--auto` | 완전 자동화 (최종 보고서만 확인) | `/work --auto "대규모 리팩토링"` |
| `--loop` | 자율 판단 루프 (기존 `/auto`) | `/work --loop` |
| `--skip-analysis` | Phase 1 스킵 | `/work --skip-analysis "빠른 수정"` |
| `--no-issue` | 이슈 생성 안함 | `/work --no-issue "내부 리팩토링"` |
| `--strict` | 엄격 모드 (E2E 1회 실패 시 중단) | `/work --strict "프로덕션 배포"` |
| `--max N` | 최대 N개 작업 후 중단 (loop 모드) | `/work --loop --max 5` |
| `--dry-run` | 판단만 보여주고 실행 안함 | `/work --loop --dry-run` |

### --auto 모드 상세

- 모든 Phase 자동 실행 (중간 확인 없음)
- 7단계 E2E Strict Validation
- 실패 시 자동 수정 (최대 3회)
- 최종 보고서만 사용자에게 제출

---

## --loop 모드 (v4.0 - 9개 커맨드 통합)

`/work --loop`는 **Ralph Wiggum 철학**을 통합한 자율 완성 모드입니다.
**"할 일 없음 → 종료"가 아니라 "할 일 없음 → 스스로 발견"**합니다.

> **핵심 원칙**: 명시적인 종료 조건이 충족될 때까지 계속 반복

### 통합 커맨드 자동 트리거

| 커맨드 | 조건 | Tier |
|--------|------|:----:|
| `/audit quick` | 세션 시작 | 0 |
| `/debug` | 테스트/빌드 실패 | 1 |
| `/check --fix` | 린트/타입 경고 10+개 | 1 |
| `/check --security` | 보안 취약점 | 1 |
| `/commit` | 변경 100줄+ | 2 |
| `/issue fix` | 열린 이슈 | 2 |
| `/pr auto` | PR 리뷰 대기 | 2 |
| `/tdd` | 새 기능 구현 | 3 |
| `/research` | 코드 분석/정보 수집 | 3 |

### 루프 서브커맨드

```bash
/work --loop                           # 자율 판단 루프 시작 (무한)
/work --loop --max 10                  # 최대 10회 반복 후 종료
/work --loop --promise "ALL_TESTS_PASS" # 조건 충족 시 종료
/work --loop resume [id]               # 세션 재개
/work --loop status                    # 현재 상태 확인
/work --loop pause                     # 일시 정지 (체크포인트 저장)
/work --loop abort                     # 세션 취소
```

### 종료 조건 (명시적으로만 종료)

| 조건 | 설명 |
|------|------|
| `--max N` | N회 반복 후 종료 |
| `--promise TEXT` | `<promise>TEXT</promise>` 출력 시 종료 |
| `pause` / `abort` | 사용자 명시적 중단 |
| Context 80% + 예상 초과 | 정리 후 자동 재시작 |
| Context 90% | 즉시 정리 후 자동 재시작 |

**⚠️ "할 일 없음"은 종료 조건이 아님** → 자율 발견 모드로 전환

### Context 예측 관리

```
Context 80% 도달
    │
    ├─ 다음 작업 예상 Context 분석
    │      │
    │      ├─ 예상 +20% 미만 → 계속 진행
    │      │
    │      └─ 예상 +20% 이상 → 정리 필요
    │              │
    │              ├─ 세션 문서 업데이트
    │              ├─ /commit 실행
    │              ├─ /clear 실행
    │              └─ /auto 재시작
```

### 5계층 우선순위 체계

```
/work --loop 실행
    │
    ├─ [Tier 0] 세션 관리
    │      └─ /audit quick (세션 시작)
    │
    ├─ [Tier 1] 긴급
    │      ├─ /debug (테스트/빌드 실패)
    │      └─ /check --fix (린트 10+개)
    │
    ├─ [Tier 2] 작업 처리
    │      ├─ /commit (변경 100줄+)
    │      ├─ /issue fix #N (열린 이슈)
    │      └─ /pr auto (PR 리뷰 대기)
    │
    ├─ [Tier 3] 개발 지원
    │      ├─ /tdd (새 기능)
    │      └─ /research (분석 필요)
    │
    ├─ [Tier 4] 자율 개선
    │      ├─ 코드 품질 (린트 경고)
    │      ├─ 테스트 커버리지
    │      └─ 문서화
    │
    └─ [Tier 4+] 자율 발견
           ├─ PRD 분석 → 개선점 탐색
           └─ 솔루션 비교 → 마이그레이션 제안
```

### 병렬 처리 (모든 Tier)

| 작업 | Agent 수 | 역할 |
|------|:--------:|------|
| `/debug` | 3 | 가설 생성 / 코드 분석 / 로그 분석 |
| `/check --e2e` | 4 | Functional / Visual / A11y / Perf |
| `/issue fix` | 3 | Coder / Tester / Reviewer |
| `/pr auto` | 4 | Security / Logic / Style / Perf |
| `/research web` | 4 | 4방향 병렬 검색 |

### 자율 발견 실행 예시

```
🔄 Iteration 3 | 명시적 작업 없음 → 자율 발견 모드

📊 자율 분석 결과:
   - ESLint 경고: 61개 (우선순위 6)
   - 테스트 커버리지: 72% (우선순위 7)
   - 문서 누락: src/api/auth.ts (우선순위 8)

🎯 선택: ESLint 경고 수정 (61개 → 0개 목표)
   └─ /issue fix #41 자동 시작...
```

### Context 모니터링 (90% 임계값)

| 사용량 | 상태 | 액션 |
|--------|------|------|
| 0-40% | safe | 정상 작업 |
| 40-60% | monitor | 주의 |
| 60-80% | prepare | 체크포인트 준비 |
| 80-90% | warning | 체크포인트 저장 |
| **90%+** | **critical** | **진행 중 작업 완료 → /commit → 세션 종료** |

### Context 90% 도달 시

```
⚠️ Context 90% 도달
   ▶ 진행 중인 작업 완료 중...
   ✅ /commit 실행
   ✅ 체크포인트 저장
   ⏹️ 세션 종료

💡 재개하려면: /work --loop resume
```

### 로그 및 체크포인트

```
.claude/auto-logs/active/session_YYYYMMDD_HHMMSS/
├── state.json           # 세션 상태
├── log_001.json         # 로그 청크 1 (50KB)
├── log_002.json         # 로그 청크 2
└── checkpoint.json      # 재개용 체크포인트
```

### 안전장치

| 상황 | 동작 |
|------|------|
| main 브랜치 직접 수정 | 브랜치 생성 후 진행 |
| 위험한 작업 (force push 등) | 스킵 + 알림 |
| 3회 연속 실패 | 루프 중단 + 수동 확인 요청 |
| 무한 루프 감지 | 자동 중단 |

---

## 공통 기능 (모든 모드)

### PRD 관리

| 단계 | 설명 |
|------|------|
| **PRD 탐색** | 기존 PRD 문서 확인 (`tasks/prds/`) |
| **PRD 작성** | 없으면 `/create prd` 자동 실행 |
| **PRD 검토** | 요구사항 완전성, 기술 실현 가능성 검토 |
| **PRD 승인** | 사용자 확인 후 구현 진행 |

### 로그 스키마

```json
{
  "timestamp": "2025-12-30T10:30:00.000Z",
  "sequence": 1,
  "event_type": "action|decision|checkpoint",
  "phase": "init|analysis|implementation|testing|complete",
  "data": {
    "action": "file_read|file_write|command|tool_use",
    "target": "path/to/file",
    "result": "success|fail"
  },
  "context_usage": 45,
  "todo_state": [...]
}
```

---

**작업 지시를 입력해 주세요. 또는 `--loop`로 자율 판단 모드를 시작하세요.**
