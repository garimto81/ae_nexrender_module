---
name: check
description: Comprehensive code quality and security checks
---

# /check - 통합 검증 커맨드

정적 분석, E2E 테스트, 성능 분석, 보안 검사를 수행합니다.

## Usage

```
/check [options]

Options:
  --fix           자동 수정 가능한 이슈 수정
  --e2e           E2E 테스트 + 자동 수정 (final-check 흡수)
  --perf          성능 분석 (optimize 흡수)
  --security      보안 검사 심화
  --api           API 엔드포인트 테스트 (api-test 흡수)
  --react         React/Next.js 성능 최적화 검사 (Vercel Best Practices)
  --all           모든 검사 수행 (security, e2e, perf, api, react 포함)

조합 사용:
  /check --e2e --fix    E2E + 자동 수정
  /check --perf --fix   성능 분석 + 자동 수정
  /check --api          REST/GraphQL API 테스트
  /check --react        React 성능 규칙 검사
  /check --react --fix  React 검사 + 제안 적용
```

## Check Categories

### 1. Static Analysis

**Python**:
```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Code style
black --check src/
```

**JavaScript/TypeScript**:
```bash
# ESLint
npm run lint

# TypeScript
npx tsc --noEmit

# Prettier
npm run format:check
```

### 2. Security Scanning

**Dependency Vulnerabilities**:
```bash
# Python
pip-audit

# Node.js
npm audit

# Severity: CRITICAL, HIGH, MODERATE, LOW
```

**SAST (Static Application Security Testing)**:
```bash
# Check for:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Hardcoded secrets
- Insecure configurations
```

### 3. Code Smells

- Duplicate code
- Long functions (>50 lines)
- High complexity (cyclomatic > 10)
- Too many parameters (>5)
- Deep nesting (>4 levels)

### 4. Test Coverage

```bash
# Python
pytest --cov=src --cov-report=term-missing

# JavaScript
npm run test:coverage

# Minimum: 80%
```

## Phase Integration

### Phase 1: Implementation
- Run `/check` before committing
- Fix issues before moving to Phase 2

### Phase 2: Testing
- `/check` validates test quality
- Coverage threshold: 80%

### Phase 5: E2E & Security
- Security scan mandatory
- No CRITICAL vulnerabilities allowed

### Phase 6: Deployment
- Final `/check` before deploy
- All checks must pass

## --all 모드 (전체 검사)

`/check --all`은 다음 검사를 모두 수행합니다:

| 검사 항목 | 개별 옵션 | 설명 |
|-----------|-----------|------|
| Static Analysis | (기본) | 타입 체크, 린트, 코드 스타일 |
| Security Scan | `--security` | 취약점, SAST 검사 |
| E2E Tests | `--e2e` | Playwright 기능/접근성 테스트 |
| Performance | `--perf` | CPU/Memory 프로파일링 |
| API Tests | `--api` | 엔드포인트 검증 |
| React Best Practices | `--react` | Vercel 49개 규칙 검사 |

```bash
# 전체 검사 실행
/check --all

# 위 명령은 아래와 동일:
/check --security --e2e --perf --api --react
```

> **Note**: `--fix`는 `--all`에 포함되지 않습니다. 자동 수정이 필요하면 명시적으로 추가하세요:
> `/check --all --fix`

---

## Output Format

```
🔍 Running Code Quality Checks...

✅ Static Analysis
   • Type checking: PASSED
   • Linting: PASSED (2 warnings)
   • Code style: PASSED

⚠️  Security Scan
   • Dependency vulnerabilities: 1 MODERATE
   • SAST: PASSED
   → Run: npm audit fix

✅ Code Smells
   • No critical issues found

✅ Test Coverage
   • Coverage: 87% (target: 80%)

Summary: 1 warning, 1 moderate issue
Action: Fix npm vulnerabilities before deploy
```

## Auto-Fix Mode

```bash
/check --fix

# Automatically fixes:
- Code formatting
- Import sorting
- Simple linting issues
- Moderate vulnerabilities (safe updates)

# Manual review needed:
- Breaking changes
- Major version updates
- Complex refactoring
```

## --e2e 모드 (E2E 테스트)

`/check --e2e`는 기존 `/final-check` 기능을 통합:

```bash
/check --e2e

# 수행 작업:
# 1. Playwright E2E 테스트 실행
# 2. 실패 시 자동 수정 시도 (최대 2회)
# 3. Visual regression 검사
# 4. 접근성 검사 (a11y)
```

### E2E 검증 기준

| 항목 | 기준 | 실패 시 |
|------|------|---------|
| Functional | 100% 통과 | 자동 수정 |
| Visual | Diff < 100px | 스냅샷 업데이트 |
| Accessibility | Violations = 0 | ARIA 추가 |
| Performance | LCP < 2.5s | 경고 |

---

## --perf 모드 (성능 분석)

`/check --perf`는 기존 `/optimize` 기능을 통합:

```bash
/check --perf

# 수행 작업:
# 1. CPU/Memory 프로파일링
# 2. 병목 지점 식별
# 3. 최적화 제안 생성
```

### 성능 기준

| 항목 | 목표 | 중요도 |
|------|------|--------|
| API 응답 | < 500ms (p95) | HIGH |
| DB 쿼리 | < 100ms | HIGH |
| 페이지 로드 | < 3s | MEDIUM |
| 메모리 사용 | < 512MB | MEDIUM |

### 최적화 제안 예시

```
⚡ Performance Analysis

🔍 Identified Issues:
   1. [CRITICAL] N+1 query in src/api/users.py:45
      → Suggestion: Use joinedload()
      → Impact: -80% query time

   2. [HIGH] Blocking I/O in src/services/fetch.py:12
      → Suggestion: Use async/await
      → Impact: -60% response time
```

---

## Integration with Agents

| 옵션 | 연동 에이전트 | 역할 |
|------|--------------|------|
| 기본 | `code-reviewer` | 코드 품질 리뷰 |
| `--security` | `security-auditor` | 보안 취약점 심층 분석 |
| `--e2e` | `test-engineer` | E2E 테스트 실행 |
| `--perf` | `devops-engineer` | 성능 분석 |
| `--react` | `frontend-dev` | React 성능 최적화 검사 |

## Related

- `/tdd` - Test-driven development
- `/work` - 전체 워크플로우

---

## --api 모드 (API 테스트)

`/check --api`는 기존 `/api-test` 기능을 통합:

```bash
/check --api                    # 전체 API 테스트
/check --api /api/users         # 특정 엔드포인트
/check --api --security         # API 보안 테스트 포함
```

### API 테스트 항목

| 카테고리 | 검사 항목 |
|----------|-----------|
| **상태 코드** | 200, 201, 400, 401, 404, 500 |
| **응답 형식** | JSON 구조, 필수 필드 |
| **인증** | 토큰 검증, 권한 확인 |
| **입력 검증** | 필수 파라미터, 타입 체크 |
| **성능** | 응답 시간 < 200ms |

### API 보안 테스트 (--api --security)

```bash
# SQL Injection 테스트
# XSS 테스트
# 인증 우회 테스트
```

---

## --react 모드 (React 성능 검사)

`/check --react`는 Vercel Engineering의 React Best Practices를 기반으로 성능 검사를 수행합니다.

```bash
/check --react                    # React 성능 규칙 검사
/check --react src/components/    # 특정 디렉토리만 검사
/check --react --perf             # 성능 분석과 함께 검사
```

### 검사 우선순위

| 우선순위 | 카테고리 | 검사 항목 |
|:--------:|----------|-----------|
| 🔴 CRITICAL | Eliminating Waterfalls | sequential await, Promise.all 미사용 |
| 🔴 CRITICAL | Bundle Size | barrel file import, dynamic import 미사용 |
| 🟠 HIGH | Server-Side | RSC 직렬화, parallel fetch, React.cache |
| 🟡 MEDIUM | Re-render | stale closure, 불필요한 리렌더링 |
| 🟢 LOW | JS Performance | 루프 최적화, Set/Map 미사용 |

### 출력 예시

```
🔍 Running React Best Practices Check...

🔴 CRITICAL Issues (2)
   1. [Waterfall] src/pages/Home.tsx:24
      → Sequential awaits detected
      → Fix: Use Promise.all() for independent operations

   2. [Bundle] src/components/Icons.tsx:1
      → Barrel file import from 'lucide-react'
      → Fix: Import directly from source files

🟠 HIGH Issues (1)
   1. [RSC] src/app/page.tsx:15
      → Passing full user object (50 fields) to client component
      → Fix: Pass only required fields

✅ MEDIUM/LOW: 3 suggestions available

Summary: 2 CRITICAL, 1 HIGH, 3 suggestions
Action: Fix CRITICAL issues before deployment
```

### 연동 스킬

`vercel-react-best-practices` 스킬의 49개 규칙을 기반으로 검사합니다.
상세 규칙은 `.claude/skills/vercel-react-best-practices/AGENTS.md` 참조.

---

## 통합 이력

| 기존 커맨드 | 통합 위치 | 날짜 |
|------------|----------|------|
| `/final-check` | `/check --e2e` | 2025-12-11 |
| `/optimize` | `/check --perf` | 2025-12-11 |
| `/api-test` | `/check --api` | 2025-12-15 |
| (신규) | `/check --react` | 2026-01-19 |
| (개선) | `--all`에 `--react` 포함 명시 | 2026-01-19 |
