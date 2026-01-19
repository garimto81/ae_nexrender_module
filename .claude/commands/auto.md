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

## 특수 기능

| 명령 | 동작 |
|------|------|
| `/auto --mockup "이름"` | `/mockup` 스킬 직접 호출 |

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
```

## 상세 문서

전체 기능은 `/work` 커맨드 참조: `.claude/commands/work.md`

---

**이 커맨드는 `/work --loop`의 alias입니다. 새 기능은 `/work`에 추가됩니다.**
