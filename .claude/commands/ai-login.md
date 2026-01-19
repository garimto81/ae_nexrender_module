---
name: ai-login
description: AI 서비스 인증 설정 (GPT, Gemini)
---

# /ai-login - AI 서비스 Browser OAuth 인증

## 사용법

```bash
/ai-login openai                    # Step 1: 브라우저 열기
/ai-login callback <URL>            # Step 2: 콜백 URL로 토큰 교환
/ai-login google                    # Google OAuth (Client ID 필요)
/ai-login status                    # 인증 상태 확인
/ai-login logout                    # 모든 세션 로그아웃
```

---

## 실행 지시 (CRITICAL)

$ARGUMENTS를 파싱하여 **Bash tool로 해당 스크립트를 직접 실행**하세요.
스크립트를 사용자에게 보여주지 말고 바로 실행하세요.

---

## openai | gpt (Step 1)

브라우저를 열고 인증 URL을 생성합니다. 사용자가 로그인 후 리다이렉트된 URL을 복사해야 합니다.

```bash
python -c "
import sys
import json
import secrets
import hashlib
import base64
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

# PKCE 생성
code_verifier = secrets.token_urlsafe(64)
digest = hashlib.sha256(code_verifier.encode()).digest()
code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
state = secrets.token_urlsafe(32)

# OpenAI OAuth 설정 (Codex CLI 호환)
CLIENT_ID = 'DRivsnm2Mu42T3KOpqdtwB3NYviHYzwD'
AUTH_ENDPOINT = 'https://auth.openai.com/authorize'
REDIRECT_URI = 'http://localhost:1455/auth/callback'
SCOPE = 'openid profile email offline_access'

# 인증 URL 생성
params = {
    'client_id': CLIENT_ID,
    'redirect_uri': REDIRECT_URI,
    'response_type': 'code',
    'scope': SCOPE,
    'state': state,
    'code_challenge': code_challenge,
    'code_challenge_method': 'S256',
}
auth_url = f'{AUTH_ENDPOINT}?{urlencode(params)}'

# 상태 저장 (Step 2에서 사용)
state_file = Path.home() / '.claude-ai-oauth-state.json'
state_file.write_text(json.dumps({
    'provider': 'openai',
    'code_verifier': code_verifier,
    'state': state,
    'client_id': CLIENT_ID,
}))

print()
print('=' * 60)
print('  OpenAI Browser OAuth - Step 1')
print('=' * 60)
print()
print('[1] 브라우저에서 OpenAI 로그인 페이지가 열립니다.')
print('[2] ChatGPT Plus/Pro 계정으로 로그인하세요.')
print('[3] 로그인 완료 후 브라우저 주소창의 URL을 복사하세요.')
print('    (localhost:1455... 또는 에러 페이지 URL)')
print()
print('[4] 복사한 URL로 다음 명령을 실행하세요:')
print()
print('    /ai-login callback <복사한 URL>')
print()
print('=' * 60)

webbrowser.open(auth_url)
print()
print('[OK] 브라우저가 열렸습니다. 로그인 후 URL을 복사하세요.')
"
```

---

## callback <URL> (Step 2 - OpenAI/Google 공용)

복사한 URL에서 인증 코드를 추출하고 토큰을 교환합니다.
저장된 상태에서 provider(openai/google)를 자동 감지합니다.

**인자**: `callback` 뒤의 모든 텍스트가 URL입니다.

```bash
python -c "
import sys
import json
import asyncio
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

# URL 인자 가져오기
callback_url = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''

if not callback_url:
    print('[ERROR] URL이 필요합니다.')
    print('사용법: /ai-login callback <URL>')
    sys.exit(1)

# 저장된 상태 로드
state_file = Path.home() / '.claude-ai-oauth-state.json'
if not state_file.exists():
    print('[ERROR] 먼저 /ai-login openai 또는 /ai-login google을 실행하세요.')
    sys.exit(1)

state_data = json.loads(state_file.read_text())
provider = state_data.get('provider', 'openai')

# URL에서 code 추출
parsed = urlparse(callback_url)
params = parse_qs(parsed.query)

if 'error' in params:
    print(f'[ERROR] OAuth 에러: {params[\"error\"][0]}')
    desc = params.get('error_description', [''])[0]
    if desc:
        print(f'        {desc}')
    sys.exit(1)

if 'code' not in params:
    print('[ERROR] URL에서 인증 코드를 찾을 수 없습니다.')
    print('        로그인 후 리다이렉트된 URL 전체를 복사했는지 확인하세요.')
    sys.exit(1)

code = params['code'][0]
print(f'[OK] 인증 코드 추출 완료 (Provider: {provider})')

# 토큰 교환
import httpx

async def exchange_token():
    sys.path.insert(0, 'C:/claude/ultimate-debate/src')
    from ultimate_debate.auth.providers.base import AuthToken
    from ultimate_debate.auth.storage import TokenStore

    # Provider별 토큰 엔드포인트
    if provider == 'google':
        token_endpoint = 'https://oauth2.googleapis.com/token'
        redirect_uri = state_data.get('redirect_uri', 'http://localhost:8080/callback')
        data = {
            'grant_type': 'authorization_code',
            'client_id': state_data['client_id'],
            'client_secret': state_data.get('client_secret', ''),
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': state_data['code_verifier'],
        }
    else:  # openai
        token_endpoint = 'https://auth.openai.com/oauth/token'
        redirect_uri = 'http://localhost:1455/auth/callback'
        data = {
            'grant_type': 'authorization_code',
            'client_id': state_data['client_id'],
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': state_data['code_verifier'],
        }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_endpoint,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

        if response.status_code != 200:
            print(f'[ERROR] 토큰 교환 실패: {response.text}')
            return False

        result = response.json()

    expires_at = datetime.now() + timedelta(seconds=result.get('expires_in', 3600))

    token = AuthToken(
        provider=provider,
        access_token=result['access_token'],
        refresh_token=result.get('refresh_token'),
        expires_at=expires_at,
        token_type=result.get('token_type', 'Bearer'),
        scopes=result.get('scope', '').split() if result.get('scope') else [],
    )

    store = TokenStore()
    await store.save(token)

    provider_name = 'OpenAI' if provider == 'openai' else 'Google'
    print()
    print(f'[SUCCESS] {provider_name} 로그인 완료!')
    print(f'   토큰 만료: {expires_at.strftime(\"%Y-%m-%d %H:%M\")}')
    print()
    if provider == 'openai':
        print('이제 /verify --provider openai로 GPT 검증을 사용할 수 있습니다.')
    else:
        print('이제 /verify --provider gemini로 Gemini 검증을 사용할 수 있습니다.')

    # 상태 파일 삭제
    state_file.unlink(missing_ok=True)
    return True

asyncio.run(exchange_token())
" "CALLBACK_URL_HERE"
```

**중요**: `CALLBACK_URL_HERE`를 $ARGUMENTS에서 `callback ` 뒤의 실제 URL로 교체하세요.

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

## google | gemini (Step 1)

Google Cloud SDK의 공개 Client ID를 사용하여 별도 설정 없이 브라우저 로그인이 가능합니다.

```bash
python -c "
import sys
import json
import secrets
import hashlib
import base64
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

# PKCE 생성
code_verifier = secrets.token_urlsafe(64)
digest = hashlib.sha256(code_verifier.encode()).digest()
code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
state = secrets.token_urlsafe(32)

# Google OAuth 설정 (Google Cloud SDK 공개 Client ID)
CLIENT_ID = '32555940559.apps.googleusercontent.com'
CLIENT_SECRET = 'ZmssLNjJy2998hD4CTg2ejr2'
AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
REDIRECT_URI = 'http://localhost:8080/callback'
# cloud-platform 스코프로 Gemini API 접근
SCOPE = 'https://www.googleapis.com/auth/cloud-platform openid email'

# 인증 URL 생성
params = {
    'client_id': CLIENT_ID,
    'redirect_uri': REDIRECT_URI,
    'response_type': 'code',
    'scope': SCOPE,
    'state': state,
    'code_challenge': code_challenge,
    'code_challenge_method': 'S256',
    'access_type': 'offline',
    'prompt': 'consent',
}
auth_url = f'{AUTH_ENDPOINT}?{urlencode(params)}'

# 상태 저장 (Step 2에서 사용)
state_file = Path.home() / '.claude-ai-oauth-state.json'
state_file.write_text(json.dumps({
    'provider': 'google',
    'code_verifier': code_verifier,
    'state': state,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri': REDIRECT_URI,
}))

print()
print('=' * 60)
print('  Google Browser OAuth - Step 1')
print('=' * 60)
print()
print('[1] 브라우저에서 Google 로그인 페이지가 열립니다.')
print('[2] Google 계정으로 로그인하세요.')
print('[3] 로그인 완료 후 브라우저 주소창의 URL을 복사하세요.')
print('    (localhost:8080... 또는 에러 페이지 URL)')
print()
print('[4] 복사한 URL로 다음 명령을 실행하세요:')
print()
print('    /ai-login callback <복사한 URL>')
print()
print('=' * 60)

webbrowser.open(auth_url)
print()
print('[OK] 브라우저가 열렸습니다. 로그인 후 URL을 복사하세요.')
"
```

---

## callback-google <URL> (Google Step 2)

Google 콜백 URL 처리. `callback`과 동일하지만 Google용 토큰 교환을 수행합니다.

**참고**: `callback` 명령은 저장된 상태에서 provider를 자동 감지하므로 OpenAI/Google 모두 `callback`으로 처리됩니다.

---

## 인증 흐름

```
/ai-login openai (또는 google)
    ↓
브라우저 열림 → 로그인
    ↓
로그인 후 리다이렉트된 URL 복사
    ↓
/ai-login callback <복사한 URL>
    ↓
토큰 저장 완료
```
