---
name: debug
description: Hypothesis-verification based debugging (Phase Gate D0-D4)
---

# /debug - 가설-검증 기반 디버깅

원인 분석 없이 수정하는 것을 방지하고, 체계적인 디버깅 프로세스를 강제합니다.

## 핵심 원칙

**수정 전에 반드시:**
1. 이슈 등록 (D0)
2. 원인 가설 작성 (D1)
3. 검증 방법 설계 (D2)
4. 가설 검증 실행 (D3)
5. 가설 확인 후 수정 (D4)

## Usage

```
/debug [description]      반자동 진행 (D0→D1→D2→D3→D4)
/debug status             현재 상태 확인
/debug abort              디버깅 세션 취소
```

---

## Phase Gate 모델

```
문제 발생
    ↓
[D0: 이슈 등록] ─── 이슈 설명 필수
    ↓ (자동)
[D1: 원인 분석] ─── 가설 작성 필수 (최소 20자)
    ↓ (자동)
[D2: 검증 설계] ─── 검증 방법 기록 필수
    ↓ (자동)
[D3: 가설 검증] ─── 결과 기록 필수
    │
    ├─ 기각 → D1로 복귀 (3회 시 /issue failed)
    │
    └─ 확인 → [D4: 수정 허용]
```

---

## 반자동 모드 동작

### Phase별 사용자 입력 요청

| Phase | 질문 | Gate 조건 |
|-------|------|----------|
| D0 | "이슈를 설명해주세요" | 설명 필수 |
| D1 | "원인 가설을 작성해주세요" | 최소 20자 |
| D2 | "이 가설을 어떻게 검증할까요?" | 검증 계획 필수 |
| D3 | "검증 결과를 입력해주세요" | confirmed/rejected |
| D4 | (자동) 수정 허용 | - |

### Gate 실패 시 동작

- 가설 미작성 → D1에서 멈춤, 가설 요청
- 검증 계획 미작성 → D2에서 멈춤, 계획 요청
- 가설 기각 → D1로 자동 복귀
- 3회 가설 기각 → `/issue failed` 자동 호출

---

## 상태 파일

디버깅 상태는 프로젝트 루트의 `.debug/` 디렉토리에 저장됩니다.

```
{project}/.debug/
├── state.json              # 현재 디버깅 상태
├── hypotheses/             # 가설 이력
│   ├── 001-hypothesis.md
│   └── 002-hypothesis.md
└── evidence/               # 검증 로그
    └── 001-evidence.txt
```

### state.json 스키마

```json
{
  "issue_id": "DEBUG-20251221-120000",
  "issue_description": "isWriting이 false인데도 수정이 안 됨",
  "current_phase": "D2_PLAN",
  "hypothesis": "메시지 감지 타이밍 문제로 isWriting이 변경 전에 체크됨",
  "hypothesis_count": 1,
  "verification_plan": "handleStreamEnd에 로그 추가하여 호출 순서 확인",
  "verification_result": null,
  "hypothesis_confirmed": false
}
```

---

## 워크플로우 예시

### 1. 디버그 세션 시작

```
> /debug "isWriting이 false인데도 수정이 안 됨"

✅ D0: 디버그 세션 시작
   Issue ID: DEBUG-20251221-120000
   설명: isWriting이 false인데도 수정이 안 됨

📝 D1: 원인 가설을 작성해주세요 (최소 20자)
```

### 2. 가설 작성 (D1)

```
> 가설: handleStreamEnd 호출 시점에 isWriting 상태가 아직 업데이트되지 않아서,
> 조건 체크에서 false가 아닌 true로 판단되는 race condition 문제

✅ D1: 가설 #1 기록됨
   저장 위치: .debug/hypotheses/001-hypothesis.md

📝 D2: 이 가설을 어떻게 검증할까요?
```

### 3. 검증 계획 (D2)

```
> 검증 방법:
> 1. handleStreamEnd 함수 진입 시점에 console.log로 isWriting 값 출력
> 2. 상태 변경 함수 호출 직후에도 로그 추가
> 3. 실제 실행하여 로그 순서 확인

✅ D2: 검증 계획 기록됨

🔍 D3: 검증을 실행하고 결과를 입력해주세요
   검증 계획: handleStreamEnd 함수 진입 시점에 console.log로...
```

### 4. 검증 실행 및 결과 (D3)

**가설 확인 시:**
```
> 결과: confirmed
> 증거: 로그에서 handleStreamEnd 호출 시 isWriting=true 확인.
>       상태 변경은 그 이후에 발생함.

✅ D3: 가설 확인됨!
   증거 저장: .debug/evidence/001-evidence.txt

🔧 D4: 수정 허용됨. 이제 코드를 수정하세요.
```

**가설 기각 시:**
```
> 결과: rejected
> 증거: 로그에서 handleStreamEnd 호출 시 이미 isWriting=false 확인.
>       타이밍 문제가 아닌 다른 원인으로 보임.

❌ D3: 가설 기각됨 (1/3)
   → D1로 복귀. 새로운 가설을 작성해주세요.
```

### 5. 3회 기각 시

```
❌ D3: 3회 가설 기각됨
   → /issue failed 호출. 수동 개입이 필요합니다.

📋 GitHub Issue 생성됨: #45 "[DEBUG] isWriting 상태 문제 - 3회 분석 실패"
```

---

## Gate 차단 예시

### D4 없이 수정 시도

```
> 코드를 수정하겠습니다.

❌ 차단됨: Phase D3 (가설 검증) 미완료
   현재 상태: D2_PLAN
   필요 조건: D3에서 hypothesis_confirmed=true

   다음 단계: /debug status로 현재 상태 확인 후 검증 진행
```

### 가설 없이 검증 시도

```
> 검증 계획: 로그 추가해서 확인

❌ 차단됨: Phase D1 (원인 분석) 미완료
   가설이 작성되지 않았습니다.

   다음 단계: 원인 가설을 먼저 작성해주세요 (최소 20자)
```

---

## /debug status - 상태 확인

```
> /debug status

📊 Debug Session Status
═══════════════════════════════════════
Issue ID: DEBUG-20251221-120000
Phase:    D2_PLAN (검증 설계)
═══════════════════════════════════════

📝 이슈 설명:
   isWriting이 false인데도 수정이 안 됨

💡 현재 가설 (#1):
   handleStreamEnd 호출 시점에 isWriting 상태가
   아직 업데이트되지 않아서...

📋 검증 계획:
   (미작성)

📈 진행 상황:
   [✓] D0: 이슈 등록
   [✓] D1: 가설 작성
   [ ] D2: 검증 설계  ← 현재
   [ ] D3: 가설 검증
   [ ] D4: 수정 허용

다음 단계: 검증 방법을 작성해주세요
```

---

## /debug abort - 세션 취소

```
> /debug abort

⚠️ 디버그 세션을 취소하시겠습니까?
   Issue ID: DEBUG-20251221-120000
   진행 상태: D2_PLAN
   가설 시도: 1회

> 확인

✅ 세션 취소됨
   아카이브: .debug/archived-DEBUG-20251221-120000.json
```

---

## 통합 워크플로우

### /work 실패 시 자동 트리거

```
/work 실행
    ↓
E2E 테스트 실패
    ↓
/debug 자동 호출
    ↓
[가설-검증 사이클]
    ↓
D4 도달 → 수정 후 /work 재개
```

### /issue fix 통합

```
/issue fix 123
    ↓
원인 분석
    ↓
confidence < 80% → /debug 자동 트리거
    ↓
[가설-검증 사이클]
    ↓
D4 도달 → 수정 진행
```

---

## 상태 관리 스크립트

`D:\AI\claude01\.claude\skills\debugging-workflow\scripts\debug_state.py`

```python
from debug_state import DebugState

# 세션 시작
state = DebugState(project_root)
state.start("이슈 설명")

# 가설 설정
state.set_hypothesis("가설 내용 (최소 20자)")

# 검증 계획 설정
state.set_verification_plan("검증 방법")

# 검증 결과 기록
state.set_verification_result("confirmed", "증거")  # 또는 "rejected"

# 수정 허용
state.advance_to_fix()

# 상태 확인
state.get_status()

# 세션 취소
state.abort()
```

---

## Related

- `/issue failed` - 3회 가설 기각 시 에스컬레이션
- `/work` - E2E 실패 시 자동 트리거
- `debugging-workflow` 스킬 - Phase D0-D4 상세
