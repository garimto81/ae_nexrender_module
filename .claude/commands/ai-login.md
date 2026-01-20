---
name: ai-login
description: AI 서비스 인증 설정 (GPT, Gemini)
---

# /ai-login - AI 서비스 Browser OAuth 인증

## 사용법

```bash
/ai-login openai                    # 자동 인증 (브라우저 → 로그인 → 완료)
/ai-login google                    # Google OAuth 자동 인증
/ai-login status                    # 인증 상태 확인
/ai-login logout                    # 모든 세션 로그아웃
```

---

## 실행 지시 (CRITICAL)

$ARGUMENTS를 파싱하여 **Bash tool로 해당 스크립트를 직접 실행**하세요.
스크립트를 사용자에게 보여주지 말고 바로 실행하세요.

---

## openai | gpt

로컬 HTTP 서버를 띄워 콜백을 자동 수신합니다. 브라우저 로그인만 하면 자동 완료됩니다.

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')

from ultimate_debate.auth.providers.openai_provider import OpenAIProvider
from ultimate_debate.auth.storage import TokenStore

async def main():
    print()
    print('=' * 60)
    print('  OpenAI Browser OAuth - Auto Mode')
    print('=' * 60)
    print()
    print('브라우저에서 로그인하면 자동으로 인증이 완료됩니다.')
    print()

    provider = OpenAIProvider()

    try:
        # use_device_code=False로 Browser OAuth 사용 (자동 콜백)
        token = await provider.login(use_device_code=False)

        # 토큰 저장
        store = TokenStore()
        await store.save(token)

        print()
        print('[SUCCESS] OpenAI 로그인 완료!')
        print(f'   토큰 만료: {token.expires_at.strftime(\"%Y-%m-%d %H:%M\")}')
        print()
        print('이제 /verify --provider openai로 GPT 검증을 사용할 수 있습니다.')

    except Exception as e:
        print(f'[ERROR] 인증 실패: {e}')
        sys.exit(1)

asyncio.run(main())
"
```

---

## status

```bash
python -c "
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')
from ultimate_debate.auth.storage import TokenStore

storage = TokenStore()

print()
print('## AI Authentication Status')
print()
print('| Provider | Status |')
print('|----------|--------|')

openai_token = storage.get_valid_token('openai')
if openai_token:
    expires = openai_token.expires_at.strftime('%Y-%m-%d %H:%M')
    print(f'| OpenAI | VALID (expires {expires}) |')
else:
    print('| OpenAI | Not logged in |')

google_token = storage.get_valid_token('google')
if google_token:
    expires = google_token.expires_at.strftime('%Y-%m-%d %H:%M')
    print(f'| Google | VALID (expires {expires}) |')
else:
    print('| Google | Not logged in |')

print()
"
```

---

## logout

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')
from ultimate_debate.auth.storage import TokenStore

async def logout():
    storage = TokenStore()
    await storage.clear_all()
    print('[OK] All AI sessions logged out.')

asyncio.run(logout())
"
```

---

## google | gemini

로컬 HTTP 서버를 띄워 콜백을 자동 수신합니다. 브라우저 로그인만 하면 자동 완료됩니다.

```bash
python -c "
import asyncio
import sys
sys.path.insert(0, 'C:/claude/ultimate-debate/src')

from ultimate_debate.auth.providers.google_provider import GoogleProvider
from ultimate_debate.auth.storage import TokenStore

async def main():
    print()
    print('=' * 60)
    print('  Google Browser OAuth - Auto Mode')
    print('=' * 60)
    print()
    print('브라우저에서 로그인하면 자동으로 인증이 완료됩니다.')
    print()

    provider = GoogleProvider()

    try:
        token = await provider.login()

        # 토큰 저장
        store = TokenStore()
        await store.save(token)

        print()
        print('[SUCCESS] Google 로그인 완료!')
        print(f'   토큰 만료: {token.expires_at.strftime(\"%Y-%m-%d %H:%M\")}')
        print()
        print('이제 /verify --provider gemini로 Gemini 검증을 사용할 수 있습니다.')

    except Exception as e:
        print(f'[ERROR] 인증 실패: {e}')
        sys.exit(1)

asyncio.run(main())
"
```

---

## 인증 흐름 (자동)

```
/ai-login openai (또는 google)
    ↓
로컬 HTTP 서버 시작 (포트 1455 또는 8080)
    ↓
브라우저 자동 열림
    ↓
사용자 로그인
    ↓
콜백 자동 수신 → 토큰 교환 → 저장 완료
```

> **이전 방식**: `/ai-login openai` → 로그인 → URL 복사 → `/ai-login callback <URL>` (2단계)
>
> **현재 방식**: `/ai-login openai` → 로그인 → 완료 (1단계)
