#!/usr/bin/env python3
"""
Daily Report Generator - 일일 종합 업무 현황 리포트

Usage:
    python daily_report.py [--gmail] [--calendar] [--github] [--all]

Options:
    --gmail     이메일 분석 포함
    --calendar  캘린더 분석 포함
    --github    GitHub 분석 포함
    --all       모든 소스 분석 (기본값)
    --json      JSON 형식 출력

Output:
    종합 업무 현황 리포트
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Windows 콘솔 UTF-8 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 스크립트 경로
SCRIPT_DIR = Path(__file__).parent
GMAIL_SCRIPT = SCRIPT_DIR / "gmail_analyzer.py"
CALENDAR_SCRIPT = SCRIPT_DIR / "calendar_analyzer.py"
GITHUB_SCRIPT = SCRIPT_DIR / "github_analyzer.py"


def run_script(script_path: Path, args: list = None) -> Optional[dict]:
    """스크립트 실행 및 JSON 결과 파싱"""
    if not script_path.exists():
        print(f"Warning: 스크립트 없음 - {script_path}")
        return None

    cmd = [sys.executable, str(script_path), "--json"]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=SCRIPT_DIR.parent,
        )

        if result.returncode != 0:
            print(f"Warning: 스크립트 실행 실패 - {script_path.name}")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return None

        # JSON 파싱 시도
        output = result.stdout.strip()
        if output:
            # stdout에서 JSON 부분만 추출 (앞의 진행 메시지 제거)
            lines = output.split("\n")
            json_start = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("[") or line.strip().startswith("{"):
                    json_start = i
                    break

            if json_start >= 0:
                json_str = "\n".join(lines[json_start:])
                return json.loads(json_str)

        return None

    except subprocess.TimeoutExpired:
        print(f"Warning: 스크립트 타임아웃 - {script_path.name}")
        return None
    except json.JSONDecodeError as e:
        print(f"Warning: JSON 파싱 실패 - {script_path.name}: {e}")
        return None
    except Exception as e:
        print(f"Warning: 스크립트 오류 - {script_path.name}: {e}")
        return None


def analyze_gmail() -> dict:
    """Gmail 분석"""
    print("📧 Gmail 분석 중...")
    data = run_script(GMAIL_SCRIPT, ["--unread", "--days", "3"])

    if not data:
        return {"tasks": [], "unanswered": []}

    # 분석 결과 정리
    tasks = [t for t in data if t.get("has_action")]
    unanswered = [
        t for t in data if t.get("is_reply_needed") and t.get("hours_since", 0) >= 48
    ]

    return {
        "tasks": sorted(
            tasks,
            key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.get("priority", "low")],
        ),
        "unanswered": unanswered,
    }


def analyze_calendar() -> dict:
    """Calendar 분석"""
    print("📅 Calendar 분석 중...")
    data = run_script(CALENDAR_SCRIPT, ["--today"])

    if not data:
        return {"events": [], "needs_prep": []}

    needs_prep = [e for e in data if e.get("needs_preparation")]

    return {
        "events": data,
        "needs_prep": needs_prep,
    }


def analyze_github() -> dict:
    """GitHub 분석"""
    print("💻 GitHub 분석 중...")
    data = run_script(GITHUB_SCRIPT, ["--days", "5"])

    if not data:
        return {"active_repos": [], "attention_needed": [], "summary": {}}

    return data


def format_report(gmail_data: dict, calendar_data: dict, github_data: dict) -> str:
    """종합 리포트 포맷팅"""
    today = datetime.now().strftime("%Y-%m-%d (%a)")
    output = [f"📊 일일 업무 현황 ({today})", "=" * 40]

    # Gmail 섹션
    gmail_tasks = gmail_data.get("tasks", [])
    gmail_unanswered = gmail_data.get("unanswered", [])

    if gmail_tasks:
        output.append("")
        output.append(f"📧 이메일 할일 ({len(gmail_tasks)}건)")
        for task in gmail_tasks[:5]:
            priority = task.get("priority", "low")
            priority_str = {"high": "긴급", "medium": "보통", "low": "낮음"}[priority]
            deadline = f" - 마감 {task['deadline']}" if task.get("deadline") else ""
            output.append(
                f"├── [{priority_str}] {task.get('subject', '')[:40]}{deadline}"
            )
            output.append(f"│       발신: {task.get('sender', 'Unknown')[:30]}")

    if gmail_unanswered:
        output.append("")
        output.append(f"⚠️ 미응답 이메일 ({len(gmail_unanswered)}건)")
        for task in gmail_unanswered[:3]:
            hours = task.get("hours_since", 0)
            output.append(f"├── {task.get('subject', '')[:40]} - {hours}시간 경과")

    # Calendar 섹션
    calendar_events = calendar_data.get("events", [])
    needs_prep = calendar_data.get("needs_prep", [])

    if calendar_events:
        output.append("")
        output.append(f"📅 오늘 일정 ({len(calendar_events)}건)")
        for event in calendar_events[:5]:
            time_str = event.get("time_str", "종일")
            summary = event.get("summary", "(제목 없음)")[:30]
            location = ""
            if event.get("conference_link"):
                location = " (온라인)"
            elif event.get("location"):
                location = f" ({event['location'][:15]})"
            output.append(f"├── {time_str} {summary}{location}")

    if needs_prep:
        output.append("")
        output.append(f"⚠️ 준비 필요 ({len(needs_prep)}건)")
        for event in needs_prep:
            output.append(f"├── {event.get('summary', '')[:40]}")

    # GitHub 섹션
    github_attention = github_data.get("attention_needed", [])
    github_active = github_data.get("active_repos", [])

    if github_attention:
        output.append("")
        output.append(f"🚨 GitHub 주의 필요 ({len(github_attention)}건)")
        for item in github_attention[:5]:
            icon = "🔀" if item.get("type") == "pr" else "🐛"
            output.append(
                f"├── {icon} #{item.get('number', 0)} ({item.get('repo', '')}): {item.get('reason', '')}"
            )
            output.append(f"│   {item.get('title', '')[:40]}")

    if github_active:
        output.append("")
        output.append(f"🔥 활발한 프로젝트 (최근 5일)")
        for repo in github_active[:5]:
            output.append(
                f"├── {repo.get('full_name', '')}: {repo.get('commits', 0)} commits, {repo.get('issues', 0)} issues"
            )

    # 요약
    output.append("")
    output.append("=" * 40)
    output.append("📈 요약")

    gmail_task_count = len(gmail_tasks)
    calendar_event_count = len(calendar_events)
    github_issue_count = len(github_attention)

    output.append(f"├── 이메일 할일: {gmail_task_count}건")
    output.append(f"├── 오늘 일정: {calendar_event_count}건")
    output.append(f"└── GitHub 주의: {github_issue_count}건")

    # 우선순위 알림
    urgent_count = len([t for t in gmail_tasks if t.get("priority") == "high"])
    urgent_count += len(github_attention)

    if urgent_count > 0:
        output.append("")
        output.append(f"⚡ 긴급 처리 필요: {urgent_count}건")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="일일 종합 업무 현황 리포트")
    parser.add_argument("--gmail", action="store_true", help="이메일 분석만")
    parser.add_argument("--calendar", action="store_true", help="캘린더 분석만")
    parser.add_argument("--github", action="store_true", help="GitHub 분석만")
    parser.add_argument("--all", action="store_true", help="모든 소스 분석 (기본값)")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    args = parser.parse_args()

    # 기본값: 모든 소스 분석
    if not any([args.gmail, args.calendar, args.github]):
        args.all = True

    print("=" * 40)
    print("📊 일일 업무 현황 리포트 생성")
    print("=" * 40)

    gmail_data = {}
    calendar_data = {}
    github_data = {}

    # 분석 실행
    if args.all or args.gmail:
        gmail_data = analyze_gmail()

    if args.all or args.calendar:
        calendar_data = analyze_calendar()

    if args.all or args.github:
        github_data = analyze_github()

    # 출력
    if args.json:
        result = {
            "generated_at": datetime.now().isoformat(),
            "gmail": gmail_data,
            "calendar": calendar_data,
            "github": github_data,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + format_report(gmail_data, calendar_data, github_data))


if __name__ == "__main__":
    main()
