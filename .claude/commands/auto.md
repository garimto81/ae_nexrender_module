---
name: auto
alias_of: "work --loop"
version: 6.0.0
description: /work --loop의 단축 명령 (자율 반복 모드)
deprecated: false
---

# /auto - 자율 반복 모드

> **`/work --loop`의 단축 명령입니다.**

## 매핑

| /auto 명령 | 실행되는 명령 |
|-----------|--------------|
| `/auto` | `/work --loop` |
| `/auto "지시"` | `/work --loop "지시"` |
| `/auto status` | `/work --loop status` |
| `/auto stop` | `/work --loop stop` |
| `/auto redirect "방향"` | `/work --loop redirect "방향"` |
| `/auto --max N` | `/work --loop --max N` |
| `/auto --debate "주제"` | 3AI 토론 즉시 실행 |

## 특수 기능

| 명령 | 동작 |
|------|------|
| `/auto --mockup "이름"` | `/mockup` 스킬 직접 호출 |
| `/auto --debate "주제"` | Ultimate Debate 3AI 토론 |

### --mockup 기본 설정

| 항목 | 기본값 | 설명 |
|------|--------|------|
| Style | `wireframe` | Black & White 와이어프레임 |
| Text & Media | 플레이스홀더 | `[Logo]`, `[Image]`, `Lorem ipsum` 등 |

> **참고**: 흑백 박스 레이아웃으로 빠르게 구조 중심 목업 생성

### --debate 사용법

```bash
# 3AI 토론 즉시 실행
/auto --debate "캐싱 전략 선택: Redis vs Memcached"

# 복잡한 아키텍처 결정
/auto --debate "마이크로서비스 vs 모놀리식 아키텍처"
```

> **참고**: `<!-- DECISION_REQUIRED -->` 마커 대신 `--debate` 플래그로 간단하게 토론 트리거

## 실행 지시

**$ARGUMENTS를 분석하여 `/work --loop`로 변환 후 Skill tool 호출:**

```python
# /auto → /work --loop
Skill(skill="work", args="--loop")

# /auto "지시" → /work --loop "지시"
Skill(skill="work", args="--loop \"$ARGUMENTS\"")

# /auto status → /work --loop status
Skill(skill="work", args="--loop status")

# /auto stop → /work --loop stop
Skill(skill="work", args="--loop stop")

# /auto --mockup "이름" → /mockup "이름"
Skill(skill="mockup", args="$NAME")

# /auto --debate "주제" → ultimate-debate 실행
Skill(skill="ultimate-debate", args="\"$TOPIC\"")
```

## 상세 문서

전체 기능은 `/work` 커맨드 참조: `.claude/commands/work.md`

---

**이 커맨드는 `/work --loop`의 alias입니다. 새 기능은 `/work`에 추가됩니다.**
