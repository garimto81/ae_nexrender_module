---
name: prd-sync
description: PRD 동기화 (Google Docs -> 로컬)
---

# /prd-sync - PRD 동기화

Google Docs 마스터 문서에서 로컬 캐시로 동기화합니다.

## Usage

```bash
/prd-sync PRD-0001           # 특정 PRD 동기화
/prd-sync --all              # 모든 PRD 동기화
/prd-sync --list             # PRD 목록 조회
```

---

## 동기화 흐름

```
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│  Google Docs    │───────▶│   prd_manager   │───────▶│  Local Cache    │
│  (마스터)       │        │   .py           │        │  (읽기 전용)    │
└─────────────────┘        └─────────────────┘        └─────────────────┘
         │                          │                          │
         │                          ▼                          │
         │                 ┌─────────────────┐                 │
         │                 │ .prd-registry   │                 │
         │                 │    .json        │                 │
         │                 └─────────────────┘                 │
         │                          │                          │
         └──────────────────────────┴──────────────────────────┘
                                    │
                                    ▼
                           Updated at: [timestamp]
```

---

## 명령어 처리

### /prd-sync PRD-NNNN

```bash
python scripts/prd_manager.py sync PRD-0001
```

**수행 작업**:
1. `.prd-registry.json`에서 PRD 정보 조회
2. Google Docs API로 문서 내용 가져오기
3. `tasks/prds/PRD-NNNN.cache.md` 업데이트
4. 레지스트리 `updated_at` 갱신

**출력 예시**:
```
[OK] Synced PRD-0001 from Google Docs
     Cache: tasks/prds/PRD-0001.cache.md
     Last Updated: 2025-12-24T12:00:00Z
```

### /prd-sync --all

모든 등록된 PRD를 순차적으로 동기화합니다.

```bash
python scripts/prd_manager.py sync --all
```

### /prd-sync --list

등록된 모든 PRD 목록을 표시합니다.

```bash
python scripts/prd_manager.py list
```

**출력 예시**:
```
PRD Registry (2 documents)
============================================================
[D] PRD-0001: After Effects Automation System
    URL: https://docs.google.com/document/d/1abc.../edit
    Priority: P0 | Updated: 2025-12-24

[P] PRD-0002: User Authentication
    URL: https://docs.google.com/document/d/2def.../edit
    Priority: P1 | Updated: 2025-12-24
```

---

## 캐시 파일 형식

동기화 후 생성되는 캐시 파일:

```markdown
<!--
  PRD-0001 Local Cache (Read-Only)
  Master: https://docs.google.com/document/d/1abc.../edit
  Last Synced: 2025-12-24T12:00:00Z
  DO NOT EDIT - Changes will be overwritten by /prd-sync
-->

# PRD-0001: After Effects Automation System

| Item | Value |
|------|-------|
| **Status** | Draft |
| **Priority** | P0 |
| **Google Docs** | [Edit Document](https://...) |

---

[Google Docs 내용이 여기에 동기화됨]

---

> **Note**: This is a read-only cache.
```

---

## 관련 파일

| 파일 | 용도 |
|------|------|
| `.prd-registry.json` | PRD 메타데이터 레지스트리 |
| `tasks/prds/PRD-NNNN.cache.md` | 로컬 캐시 (읽기 전용) |
| `docs/checklists/PRD-NNNN.md` | 진행 체크리스트 |
| `scripts/prd_manager.py` | PRD 관리 스크립트 |

---

## 주의사항

- 로컬 캐시 파일을 직접 수정하지 마세요
- 수정은 항상 Google Docs에서 진행
- 동기화 전 Google Docs 저장 확인

---

## Related

- `/create prd` - PRD 생성
- `/todo generate PRD-NNNN` - PRD에서 Task 생성
