# 일일 업무 현황 리포트

**생성일시**: {{generated_at}}

---

## 📧 이메일 할일

{{#gmail_tasks}}
- [{{priority}}] {{subject}}
  - 발신: {{sender}}
  - 마감: {{deadline}}
{{/gmail_tasks}}

{{^gmail_tasks}}
- 할일이 있는 이메일이 없습니다.
{{/gmail_tasks}}

---

## ⚠️ 미응답 이메일

{{#gmail_unanswered}}
- {{subject}} - {{hours_since}}시간 경과
{{/gmail_unanswered}}

---

## 📅 오늘 일정

{{#calendar_events}}
- {{time_str}} {{summary}} {{location}}
{{/calendar_events}}

{{^calendar_events}}
- 오늘 예정된 일정이 없습니다.
{{/calendar_events}}

---

## 💻 GitHub 현황

### 주의 필요
{{#github_attention}}
- [{{type}}] #{{number}} ({{repo}}): {{reason}}
  {{title}}
{{/github_attention}}

### 활발한 프로젝트
{{#github_active}}
- {{full_name}}: {{commits}} commits, {{issues}} issues
{{/github_active}}

---

## 📊 요약

| 항목 | 건수 |
|------|------|
| 이메일 할일 | {{gmail_task_count}} |
| 오늘 일정 | {{calendar_event_count}} |
| GitHub 주의 | {{github_attention_count}} |

---

*이 리포트는 Secretary Skill에 의해 자동 생성되었습니다.*
