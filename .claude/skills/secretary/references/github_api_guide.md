# GitHub REST API 가이드

Secretary Skill에서 사용하는 GitHub API 참조 문서입니다.

## 인증

### Personal Access Token (PAT)

```bash
# 환경 변수 설정
set GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# 또는 파일 저장
echo "ghp_xxxxxxxxxxxx" > C:\claude\json\github_token.txt
```

### 필요한 권한 (Scopes)

| Scope | 설명 | 필수 여부 |
|-------|------|----------|
| `repo` | Private 레포지토리 전체 접근 | 필수 |
| `read:user` | 사용자 프로필 읽기 | 권장 |
| `read:org` | 조직 정보 읽기 | 선택 |

### 요청 헤더

```python
headers = {
    "Authorization": "Bearer ghp_xxxxxxxxxxxx",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
```

---

## 주요 API 엔드포인트

### 사용자 레포지토리 목록

```http
GET /user/repos
```

**Parameters:**
| 이름 | 타입 | 설명 |
|------|------|------|
| `sort` | string | 정렬 기준: `pushed`, `created`, `updated` |
| `per_page` | int | 페이지당 결과 수 (최대 100) |
| `page` | int | 페이지 번호 |

**Response:**
```json
[
  {
    "id": 123456,
    "name": "repo-name",
    "full_name": "owner/repo-name",
    "pushed_at": "2026-01-09T10:00:00Z",
    "stargazers_count": 10
  }
]
```

---

### 커밋 목록

```http
GET /repos/{owner}/{repo}/commits
```

**Parameters:**
| 이름 | 타입 | 설명 |
|------|------|------|
| `since` | string | 이 날짜 이후 커밋 (ISO 8601) |
| `until` | string | 이 날짜 이전 커밋 |
| `per_page` | int | 페이지당 결과 수 |

**Example:**
```bash
# 최근 5일 커밋
GET /repos/owner/repo/commits?since=2026-01-04T00:00:00Z
```

**Response:**
```json
[
  {
    "sha": "abc123",
    "commit": {
      "message": "Fix bug",
      "author": {
        "name": "Developer",
        "date": "2026-01-09T10:00:00Z"
      }
    }
  }
]
```

---

### 이슈 목록

```http
GET /repos/{owner}/{repo}/issues
```

**Parameters:**
| 이름 | 타입 | 설명 |
|------|------|------|
| `state` | string | `open`, `closed`, `all` |
| `since` | string | 이 날짜 이후 업데이트된 이슈 |
| `per_page` | int | 페이지당 결과 수 |

**Note:** Pull Request도 이슈로 반환됩니다. `pull_request` 필드가 있으면 PR입니다.

**Response:**
```json
[
  {
    "number": 42,
    "title": "Bug report",
    "state": "open",
    "created_at": "2026-01-05T10:00:00Z",
    "updated_at": "2026-01-09T10:00:00Z"
  }
]
```

---

### Pull Request 목록

```http
GET /repos/{owner}/{repo}/pulls
```

**Parameters:**
| 이름 | 타입 | 설명 |
|------|------|------|
| `state` | string | `open`, `closed`, `all` |
| `per_page` | int | 페이지당 결과 수 |

**Response:**
```json
[
  {
    "number": 43,
    "title": "Add feature",
    "state": "open",
    "created_at": "2026-01-06T10:00:00Z",
    "html_url": "https://github.com/owner/repo/pull/43"
  }
]
```

---

## Rate Limits

| 인증 상태 | 제한 |
|-----------|------|
| 비인증 | 60 requests/hour |
| PAT 인증 | 5,000 requests/hour |
| OAuth App | 5,000 requests/hour/user |

### Rate Limit 확인

```http
GET /rate_limit
```

**Response:**
```json
{
  "rate": {
    "limit": 5000,
    "remaining": 4999,
    "reset": 1704800000
  }
}
```

---

## 에러 처리

| 상태 코드 | 의미 | 대응 |
|-----------|------|------|
| 401 | 인증 실패 | 토큰 확인 |
| 403 | Rate limit 또는 권한 없음 | 대기 또는 권한 확인 |
| 404 | 리소스 없음 | 경로 확인 |
| 422 | 유효하지 않은 요청 | 파라미터 확인 |

---

## 참조

- [GitHub REST API 문서](https://docs.github.com/en/rest)
- [Commits API](https://docs.github.com/en/rest/commits/commits)
- [Issues API](https://docs.github.com/en/rest/issues/issues)
- [Pull Requests API](https://docs.github.com/en/rest/pulls/pulls)
