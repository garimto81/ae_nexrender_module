---
name: verify
description: Cross-AI Verifier로 코드 검증 (GPT, Gemini)
---

# /verify - 다중 AI 코드 검증 커맨드

외부 AI 모델(OpenAI GPT, Google Gemini)을 사용하여 코드를 교차 검증합니다.
**API 키 환경변수 방식으로 인증합니다.**

## Usage

```bash
/verify <file_or_directory> [options]

Options:
  --provider <name>    사용할 AI Provider (openai, gemini)
  --focus <type>       검증 초점 (security, bugs, performance, all)
  --parallel           모든 Provider 동시 검증
```

## Examples

```bash
# 단일 파일 검증
/verify src/auth.py --focus security --provider openai

# 디렉토리 검증
/verify tests/ --focus bugs --provider gemini

# 병렬 검증 (OpenAI + Gemini 동시)
/verify src/ --parallel --focus all
```

## 검증 Focus

| Focus | 설명 | 검사 항목 |
|-------|------|----------|
| `security` | 보안 취약점 분석 | SQL Injection, XSS, CSRF, 권한 검증 |
| `bugs` | 논리 오류 검사 | 경계 조건, null 체크, 타입 오류 |
| `performance` | 성능 이슈 분석 | N+1 쿼리, 메모리 누수, 복잡도 |
| `all` | 종합 코드 리뷰 | 위 모든 항목 + 코드 스타일 |

## 지원 Provider

| Provider | 모델 | 인증 방법 |
|----------|------|----------|
| **openai** | GPT-4 | 환경변수 `OPENAI_API_KEY` |
| **gemini** | Gemini Pro | 환경변수 `GEMINI_API_KEY` |

## 인증 설정 (필수)

API 키를 환경변수로 설정하세요:

```powershell
# PowerShell (현재 세션만)
$env:OPENAI_API_KEY = "<YOUR_API_KEY>"
$env:GEMINI_API_KEY = "<YOUR_API_KEY>"
```

> ⚠️ **보안 주의사항**
> - 셸 히스토리에 API 키가 남을 수 있습니다
> - 권장: `.env` 파일 사용 후 `.gitignore`에 등록
> - 또는 Windows Credential Manager / Secret Manager 사용

설정 안내를 보려면:

```bash
/ai-login gpt      # OpenAI API 키 설정 방법
/ai-login gemini   # Gemini API 키 설정 방법
/ai-login status   # 현재 설정 상태 확인
```

> ⚠️ API 키가 설정되지 않으면 검증이 실행되지 않습니다.

---

## 실행 지시

파라미터를 분석하여 Cross-AI Verifier Skill을 실행하세요.

### STEP 1: 파라미터 파싱

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `<target>` | (필수) | 검증할 파일 또는 디렉토리 |
| `--provider` | `openai` | 사용할 Provider |
| `--focus` | `all` | 검증 초점 |
| `--parallel` | `false` | 병렬 검증 여부 |

### STEP 2: 타겟 코드 읽기

```python
# 파일인 경우
code = Read(file_path=target)

# 디렉토리인 경우
files = Glob(pattern=f"{target}/**/*.py")  # Python 예시
for file in files:
    code = Read(file_path=file)
```

### STEP 3: ProviderRouter로 검증

```python
from providers.router import ProviderRouter
from prompts.verify_prompt import build_verify_prompt

router = ProviderRouter()  # API 키 환경변수에서 자동 로드

if parallel:
    results = await router.verify_parallel(code, prompt, language=language)
    aggregated = router.aggregate_results(results)
else:
    result = await router.verify(code, provider, prompt, language=language)
```

### STEP 4: 결과 보고

```markdown
## Cross-AI Verifier 검증 결과

### 검증 대상
| 항목 | 값 |
|------|-----|
| 파일 | {target} |
| 언어 | {language} |
| Focus | {focus} |
| Provider | {provider(s)} |

### 발견된 이슈 ({count}개)

| 심각도 | 라인 | 설명 | Source |
|--------|------|------|--------|
| {severity} | {line} | {message} | {provider} |

### 제안 사항
- {suggestion 1}
- {suggestion 2}

### 신뢰도
{avg_confidence}%

---

**다음 단계**
- 수정 적용: 발견된 이슈를 수정하세요
- 재검증: `/verify {target} --focus {focus}`
```

---

## 출력 예시

```markdown
## Cross-AI Verifier 검증 결과

### 검증 대상
| 항목 | 값 |
|------|-----|
| 파일 | src/auth.py |
| 언어 | Python |
| Focus | security |
| Provider | openai, gemini |

### 발견된 이슈 (3개)

| 심각도 | 라인 | 설명 | Source |
|--------|------|------|--------|
| 🔴 High | 45 | SQL Injection 취약점 - 사용자 입력 직접 쿼리 | openai, gemini |
| 🟡 Medium | 78 | 하드코딩된 비밀번호 | openai |
| 🟢 Low | 120 | 불필요한 권한 체크 | gemini |

### 제안 사항
- 파라미터화된 쿼리 사용
- 환경 변수로 비밀번호 관리
- 권한 체크 로직 리팩토링

### 신뢰도
87.5%
```

---

## 관련 파일

| 경로 | 설명 |
|------|------|
| `.claude/skills/cross-ai-verifier/` | Cross-AI Verifier Skill |
| `.claude/commands/ai-login.md` | API 키 설정 안내 |
