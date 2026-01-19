# /ai-login - AI Provider 인증

Browser OAuth 기반 AI Provider 인증 커맨드.

## 사용법

```
/ai-login <provider>
/ai-login status
```

### Provider 옵션

| Provider | 별칭 | 설명 |
|----------|------|------|
| `openai` | `gpt` | ChatGPT Plus/Pro 계정 인증 |
| `google` | `gemini` | Google 계정 OAuth 인증 |
| `status` | - | 저장된 토큰 상태 확인 |

## 실행 지시

**CRITICAL**: 아래 스크립트를 사용자에게 보여주지 말고, **Bash tool로 직접 실행**하세요.

$ARGUMENTS를 파싱하여 해당하는 스크립트를 실행하세요.

---

### openai | gpt

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')
from ultimate_debate.auth.providers import OpenAIProvider
from ultimate_debate.auth.storage import TokenStore

async def login():
    provider = OpenAIProvider()
    print('[INFO] OpenAI Device Code Flow 시작...')
    print('[INFO] 브라우저에서 인증 페이지가 열립니다.')
    token = await provider.login()
    store = TokenStore()
    await store.save(token)
    print(f'[SUCCESS] OpenAI 로그인 완료!')
    print(f'[INFO] 토큰 만료: {token.expires_at}')

asyncio.run(login())
"
```

---

### google | gemini

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')
from ultimate_debate.auth.providers import GoogleProvider
from ultimate_debate.auth.storage import TokenStore

async def login():
    provider = GoogleProvider()
    print('[INFO] Google OAuth Flow 시작...')
    print('[INFO] 브라우저에서 인증 페이지가 열립니다.')
    token = await provider.login()
    store = TokenStore()
    await store.save(token)
    print(f'[SUCCESS] Google 로그인 완료!')
    print(f'[INFO] 토큰 만료: {token.expires_at}')

asyncio.run(login())
"
```

---

### status

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')
from ultimate_debate.auth.storage import TokenStore

async def check_status():
    store = TokenStore()

    print('=== AI Provider 토큰 상태 ===\n')

    for provider in ['openai', 'google']:
        token = await store.load(provider)
        if token:
            status = 'EXPIRED' if token.is_expired() else 'VALID'
            print(f'[{provider.upper()}] {status}')
            print(f'  - 만료: {token.expires_at}')
        else:
            print(f'[{provider.upper()}] NOT_FOUND')
        print()

asyncio.run(check_status())
"
```

---

## 인증 정책

| 규칙 | 설명 |
|------|------|
| **API 키 금지** | OPENAI_API_KEY 등 환경변수 사용 금지 |
| **Browser OAuth만** | 구독 기반 인증만 허용 |
| **토큰 저장** | OS 자격증명 저장소 (keyring) 사용 |

## 예시

```
/ai-login openai    # OpenAI Device Code 인증
/ai-login google    # Google OAuth 인증
/ai-login status    # 토큰 상태 확인
```
