---
name: audit
description: Daily configuration audit and improvement suggestions
---

# /audit - 일일 설정 점검

CLAUDE.md, 커맨드, 에이전트, 스킬의 일관성과 품질을 점검합니다.

## Usage

```bash
/audit              # 전체 점검
/audit quick        # 빠른 점검 (버전/개수만)
/audit deep         # 심층 점검 (내용 분석 포함)
/audit fix          # 발견된 문제 자동 수정
/audit baseline     # 현재 상태를 기준으로 저장

# 솔루션 추천 (신규)
/audit suggest              # 전체 영역 솔루션 추천
/audit suggest security     # 보안 도구 추천
/audit suggest ci-cd        # CI/CD 도구 추천
/audit suggest code-review  # 코드 리뷰 도구 추천
/audit suggest mcp          # MCP 서버 추천
/audit suggest deps         # 의존성 관리 도구 추천
/audit suggest --save       # 추천 결과 저장
```

## 점검 항목

### 1. CLAUDE.md 검사

| 항목 | 검사 내용 |
|------|----------|
| 버전 | 버전 번호 존재 여부 |
| 커맨드 개수 | 기재된 개수 vs 실제 파일 수 |
| 에이전트 개수 | 기재된 개수 vs 실제 파일 수 |
| 스킬 개수 | 기재된 개수 vs 실제 파일 수 |

### 2. 커맨드 검사 (`.claude/commands/*.md`)

| 항목 | 검사 내용 |
|------|----------|
| frontmatter | `---` 블록 존재 |
| name 필드 | `name:` 정의 |
| description 필드 | `description:` 정의 |
| Usage 섹션 | 사용법 문서화 |

### 3. 에이전트 검사 (`.claude/agents/*.md`)

| 항목 | 검사 내용 |
|------|----------|
| 역할 정의 | Role/역할 섹션 |
| 전문 분야 | Expertise/전문 분야 섹션 |
| 도구 정의 | Tools/도구 섹션 |

### 4. 스킬 검사 (`.claude/skills/*/SKILL.md`)

| 항목 | 검사 내용 |
|------|----------|
| SKILL.md | 파일 존재 |
| 트리거 조건 | trigger/트리거 정의 |

### 5. 문서 동기화 검사

| 문서 | 검사 내용 |
|------|----------|
| COMMAND_REFERENCE.md | 모든 커맨드 포함 |
| AGENTS_REFERENCE.md | 모든 에이전트 포함 |

## 점검 흐름

```
/audit 실행
    │
    ├─ [1/5] CLAUDE.md 점검
    │       ├─ 버전 확인
    │       ├─ 커맨드 개수 일치
    │       ├─ 에이전트 개수 일치
    │       └─ 스킬 개수 일치
    │
    ├─ [2/5] 커맨드 점검
    │       ├─ 파일별 frontmatter
    │       └─ 필수 섹션 확인
    │
    ├─ [3/5] 에이전트 점검
    │       └─ 파일별 필수 섹션
    │
    ├─ [4/5] 스킬 점검
    │       └─ SKILL.md 존재 및 내용
    │
    └─ [5/5] 문서 동기화 점검
            ├─ COMMAND_REFERENCE.md
            └─ AGENTS_REFERENCE.md
```

## 출력 형식

### 정상 시

```
🔍 Configuration Audit - 2025-12-12

[1/5] CLAUDE.md 점검...
  ✅ 버전: 10.1.0
  ✅ 커맨드: 14개 일치
  ✅ 에이전트: 18개 일치
  ✅ 스킬: 13개 일치

[2/5] 커맨드 점검...
  ✅ 14개 파일 검사 완료

[3/5] 에이전트 점검...
  ✅ 18개 파일 검사 완료

[4/5] 스킬 점검...
  ✅ 13개 디렉토리 검사 완료

[5/5] 문서 동기화 점검...
  ✅ COMMAND_REFERENCE.md 동기화됨
  ✅ AGENTS_REFERENCE.md 동기화됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 모든 점검 통과
   총 검사: 5개 영역
   문제: 0개
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 문제 발견 시

```
🔍 Configuration Audit - 2025-12-12

[1/5] CLAUDE.md 점검...
  ✅ 버전: 10.1.0
  ⚠️ 커맨드 개수 불일치: 문서 13개, 실제 14개
  ✅ 에이전트: 18개 일치
  ✅ 스킬: 13개 일치

[2/5] 커맨드 점검...
  ✅ 14개 파일 검사 완료

[3/5] 에이전트 점검...
  ✅ 18개 파일 검사 완료

[4/5] 스킬 점검...
  ✅ 13개 디렉토리 검사 완료

[5/5] 문서 동기화 점검...
  ⚠️ COMMAND_REFERENCE.md에 /audit 누락
  ✅ AGENTS_REFERENCE.md 동기화됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 2개 문제 발견

1. CLAUDE.md 커맨드 개수 업데이트 필요
   현재: 13개 → 수정: 14개

2. COMMAND_REFERENCE.md 업데이트 필요
   누락: /audit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
자동 수정을 실행할까요? (Y/N)
```

## 자동 수정 가능 항목

| 항목 | 자동 수정 | 설명 |
|------|----------|------|
| 개수 불일치 | ✅ | CLAUDE.md의 개수 숫자 업데이트 |
| 버전 업데이트 | ✅ | 패치 버전 자동 증가 |
| 문서 동기화 | ✅ | 누락된 항목 추가 |
| frontmatter 누락 | ❌ | 수동 작성 필요 |
| 내용 개선 | ❌ | 수동 검토 필요 |

## /audit deep - 심층 점검

추가로 다음을 검사합니다:

- 커맨드 간 중복 기능 감지
- 에이전트 역할 중복 검사
- 스킬 트리거 충돌 검사
- 사용되지 않는 파일 감지

## /audit baseline - 기준 상태 저장

현재 상태를 기준으로 저장하여 향후 Drift(변경) 감지에 활용합니다.

```bash
/audit baseline

# 출력:
# ✅ 기준 상태 저장됨
# 📁 .claude/baseline/config-baseline.yaml
# - CLAUDE.md: checksum abc123
# - 커맨드: 14개
# - 에이전트: 18개
# - 스킬: 13개
```

## 권장 사용 시점

| 시점 | 권장 명령 |
|------|----------|
| 매일 작업 시작 | `/audit quick` |
| 커맨드/에이전트 수정 후 | `/audit` |
| 주간 점검 | `/audit deep` |
| 릴리즈 전 | `/audit deep` |

---

## /audit suggest - 솔루션 추천 (신규)

웹과 GitHub를 검색하여 현재 프로젝트에 적합한 최신 도구/솔루션을 추천합니다.

### 추천 영역

| 영역 | 검색 대상 | 추천 내용 |
|------|----------|----------|
| `security` | Snyk, Semgrep, Gitleaks | SAST, 의존성 취약점, 시크릿 스캐닝 |
| `ci-cd` | GitHub Actions, Spacelift, Harness | CI/CD 파이프라인, GitOps |
| `code-review` | Qodo Merge, CodeRabbit, Codacy | AI 코드 리뷰, 자동 PR 분석 |
| `mcp` | MCP Stack, Stainless | Claude Code MCP 서버 |
| `deps` | Dependabot, Renovate | 의존성 자동 업데이트 |

### 추천 흐름

```
/audit suggest [영역] 실행
    │
    ├─ [1/4] 현재 설정 분석
    │       ├─ MCP 서버 목록 (.claude.json)
    │       ├─ 사용 중인 도구 (ruff, pytest 등)
    │       └─ package.json / pyproject.toml
    │
    ├─ [2/4] GitHub 트렌드 검색
    │       ├─ gh api search/repositories
    │       └─ 스타 수, 최근 업데이트 기준
    │
    ├─ [3/4] 웹 검색 (Exa MCP)
    │       ├─ "[영역] best tools 2025"
    │       └─ 최신 블로그/문서 분석
    │
    └─ [4/4] 추천 리포트 생성
            ├─ 현재 스택과의 호환성
            ├─ Make vs Buy 분석
            └─ 설치/설정 가이드
```

### 출력 예시

```
🔍 Solution Recommendations - Security
Date: 2025-12-12

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 현재 상태
✅ 사용 중: ruff (린트), pip-audit (의존성)
⚠️ 부족: SAST, 시크릿 스캐닝

## 추천 솔루션

### 1. Snyk (⭐ 강력 추천)
├─ 용도: 의존성 취약점 + 컨테이너 보안
├─ GitHub Stars: 5.2K+
├─ 호환성: ✅ Python, Node.js 지원
└─ 설치:
   npm install -g snyk
   snyk auth && snyk test

### 2. Semgrep
├─ 용도: 커스텀 룰 기반 SAST
├─ GitHub Stars: 10K+
└─ 설치:
   pip install semgrep
   semgrep --config=auto .

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Make vs Buy 분석

| 항목 | Make | Buy (Snyk) |
|------|------|------------|
| 초기 비용 | 높음 | 낮음 |
| 유지보수 | 직접 | 자동 |
| 권장 | ❌ | ✅ |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sources:
- https://snyk.io/
- https://semgrep.dev/
```

### /audit suggest mcp - MCP 서버 추천

```
🔍 Solution Recommendations - MCP Servers

## 현재 MCP 설정
✅ context7, sequential-thinking, taskmanager, exa

## 추천 MCP 서버

### 1. github-mcp-server (⭐ 강력 추천)
├─ 용도: GitHub API 90+ 도구 통합
├─ 기능: PR, Issue, Actions, Releases
└─ 설치:
   claude mcp add github --transport http \
     https://api.githubcopilot.com/mcp/

### 2. postgres-mcp
├─ 용도: PostgreSQL 직접 쿼리
└─ 설치:
   claude mcp add postgres -- npx -y @modelcontextprotocol/server-postgres

## 워크플로우 개선 효과

| MCP 추가 | 개선되는 커맨드 |
|----------|----------------|
| github | /issue, /pr, /work |
| postgres | /research code --deps |
```

### --save 옵션

추천 결과를 파일로 저장합니다.

```bash
/audit suggest security --save

# 저장 위치: .claude/research/audit-suggest-security-2025-12-12.md
```

---

## Related

- `/check` - 코드 품질 검사
- `/research web` - 웹 리서치
- `/session compact` - 세션 관리
- `docs/DAILY_IMPROVEMENT_SYSTEM.md` - 자동화 시스템 상세
