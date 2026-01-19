---
name: session
description: 세션 관리 통합 (compact, journey, changelog, resume)
---

# /session - 세션 관리 통합 커맨드

컨텍스트 압축, 세션 여정 기록, 변경 로그, 세션 이어가기를 관리합니다.

## Usage

```
/session [subcommand] [options]

Subcommands:
  compact [options]   컨텍스트 압축
  journey [options]   세션 여정 기록
  changelog [version] 변경 로그 생성
  resume [options]    이전 세션 이어가기 ⭐NEW
  save                세션 상태 저장 (종료 전)

기본 동작:
  /session            = /session journey (현재 세션 기록)
```

---

## /session save - 세션 상태 저장 ⭐

세션 종료 전 현재 작업 상태를 저장하여 다음 세션에서 이어갈 수 있습니다.

```bash
/session save                 # 현재 상태 저장
/session save "작업 설명"      # 설명과 함께 저장
```

### 저장 내용

1. **진행 중인 작업** - 현재 태스크, 미완료 항목
2. **컨텍스트** - 핵심 파일, 의사결정, 브랜치 정보
3. **다음 단계** - 이어서 해야 할 작업

### 저장 파일 형식

```markdown
# Session State: 2025-12-11 15:30

## 현재 작업
- **Issue**: #42 - 인증 기능 구현
- **Branch**: feat/issue-42-auth
- **진행률**: 60%

## 완료된 항목
- [x] API 엔드포인트 설계
- [x] 데이터베이스 스키마 생성

## 미완료 항목
- [ ] JWT 토큰 발급 로직
- [ ] 테스트 코드 작성

## 핵심 컨텍스트
- 파일: `src/auth/handler.py` - 메인 로직
- 결정: Supabase Auth 대신 커스텀 JWT 사용

## 다음 단계
1. `generate_token()` 함수 구현
2. 만료 시간 설정 (24시간)
3. 단위 테스트 작성

## 메모
- refresh token은 다음 PR에서 처리
```

---

## /session resume - 세션 이어가기 ⭐

저장된 세션 상태를 로드하여 작업을 이어갑니다.

```bash
/session resume               # 최근 세션 로드
/session resume list          # 저장된 세션 목록
/session resume [date]        # 특정 날짜 세션 로드
/session resume [filename]    # 특정 파일 로드
```

### 동작 방식

1. `.claude/sessions/` 에서 저장된 상태 파일 검색
2. 세션 상태 로드 및 표시
3. 미완료 항목을 TodoWrite로 자동 등록
4. 컨텍스트 복원 (핵심 파일 요약)

### 예시 출력

```
📂 Loading session: 2025-12-11-auth-feature.md

## 이전 세션 요약
- Issue #42: 인증 기능 구현 (60% 완료)
- Branch: feat/issue-42-auth

## 미완료 작업 (자동 등록됨)
1. JWT 토큰 발급 로직 구현
2. 테스트 코드 작성

## 핵심 컨텍스트
- src/auth/handler.py - 메인 로직 파일

이어서 작업하시겠습니까? (Y/n)
```

---

## /session compact - 컨텍스트 압축

세션 컨텍스트를 압축하여 성능을 유지합니다.

```bash
/session compact              # 즉시 압축
/session compact save         # 압축 결과 저장
/session compact load [date]  # 저장된 압축 로드
/session compact status       # 현재 상태 확인
```

### Context Engineering 임계값

| 사용량 | 상태 | 권장 조치 |
|--------|------|-----------|
| 0-40% | 🟢 Safe | 정상 작업 |
| 40-60% | 🟡 DUMB | 주의 - 성능 저하 시작 |
| 60-80% | 🟠 COMPRESS | `/session compact` 권장 |
| 80%+ | 🚨 CRITICAL | 즉시 압축 필요 |

### 압축 대상 vs 보존 항목

| 압축 대상 | 보존 항목 |
|----------|----------|
| 완료된 태스크 → 요약 | 현재 진행 중 태스크 |
| 탐색된 파일 → 경로만 | 핵심 의사결정 |
| 에러 로그 → 핵심만 | 미해결 이슈 |
| 서브에이전트 결과 → 요약 | |

### 저장 형식

```markdown
# Session Compact: 2025-12-11

## 작업 요약
- Issue #30 구현 완료
- 3개 파일 생성, 1개 수정

## 핵심 결정
- 여정 섹션을 PR 템플릿 상단에 배치

## 미해결 사항
- 없음

## 컨텍스트
- 시작: 12%
- 최대: 65%
- 압축 후: 15%
```

---

## /session journey - 세션 여정 기록

현재 세션의 작업 여정을 기록하고 PR에 첨부합니다.

```bash
/session journey              # 현재 세션 표시 (기본값)
/session journey save         # 세션 저장
/session journey show         # 저장된 목록
/session journey export       # PR용 마크다운 생성
/session journey clear        # 기록 초기화
```

### 자동 수집 항목

| 항목 | 설명 |
|------|------|
| `milestones` | 주요 작업 단계 |
| `decisions` | 의사결정 기록 |
| `files_changed` | 변경된 파일 목록 |
| `context_usage` | 컨텍스트 사용량 |
| `blockers` | 발견된 장애물 |

### PR 연동

`/create pr` 실행 시 자동으로 여정 섹션이 포함됩니다.

```markdown
## 여정 (Journey)

### 작업 흐름
1. 19:00 - Plan 시작 (context: 12%)
2. 19:15 - 코드베이스 분석
3. 19:30 - 구현 완료

### 주요 결정
- **A vs B**: A 선택 (이유: 성능 우선)

### 변경 파일
- `file1.py` - 핵심 로직
- `file2.md` - 문서
```

---

## /session changelog - 변경 로그 생성

커밋 히스토리를 분석하여 CHANGELOG.md를 업데이트합니다.

```bash
/session changelog            # Unreleased에 추가
/session changelog 1.2.0      # 특정 버전으로 릴리즈
```

### Changelog 형식 (Keep a Changelog)

```markdown
# Changelog

## [Unreleased]

### Added
- 새 기능

### Changed
- 기존 기능 변경

### Fixed
- 버그 수정

## [1.0.0] - 2025-01-18

### Added
- Initial release
```

### 커밋 타입 자동 분류

| 커밋 접두어 | Changelog 섹션 |
|------------|----------------|
| `feat:` | Added |
| `fix:` | Fixed |
| `docs:` | Changed |
| `refactor:` | Changed |
| `perf:` | Changed |
| `test:` | Added (tests) |
| `chore:` | (생략) |

### PRD 연동

```markdown
### Added
- 새 인증 기능 [PRD-0001](tasks/prds/0001-prd-auth.md)
```

---

## 저장 위치

```
.claude/
├── compacts/
│   ├── 2025-12-11-session.md
│   └── ...
├── sessions/
│   ├── 2025-12-11-session.json
│   └── ...
└── research/
    └── ...
```

---

## Best Practices

1. **40% 도달 시**: `/session compact` 계획
2. **60% 도달 시**: 태스크 완료 후 즉시 압축
3. **세션 종료 시**: `/session save`로 상태 저장 ⭐
4. **세션 시작 시**: `/session resume`로 이전 작업 이어가기 ⭐
5. **릴리즈 전**: `/session changelog [version]` 실행

### 권장 워크플로우

```
[세션 시작]
/session resume              # 이전 작업 불러오기
↓
[작업 진행]
... 코드 작성 ...
↓
[세션 종료 전]
/session save "인증 기능 70% 완료"
↓
[다음 세션]
/session resume              # 자동으로 이어서 시작
```

---

## Related

- `/work` - 전체 워크플로우
- `/create pr` - PR 생성 (여정 자동 포함)
- `/commit` - 커밋 생성

---

## 통합 이력

| 기존 커맨드 | 통합 위치 | 날짜 |
|------------|----------|------|
| `/compact` | `/session compact` | 2025-12-11 |
| `/journey` | `/session journey` | 2025-12-11 |
| `/changelog` | `/session changelog` | 2025-12-11 |
| (신규) | `/session save` | 2025-12-11 |
| (신규) | `/session resume` | 2025-12-11 |
