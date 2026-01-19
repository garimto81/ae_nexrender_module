#!/usr/bin/env python3
"""
Gmail Analyzer - 이메일에서 할일/마감일 자동 추출

Usage:
    python gmail_analyzer.py [--unread] [--days N] [--max N]

Options:
    --unread    미읽은 이메일만 분석 (기본값)
    --days N    최근 N일 이메일 분석 (기본: 3일)
    --max N     최대 N개 이메일 분석 (기본: 20)

Output:
    JSON 형식의 할일 목록 또는 포맷된 텍스트 출력
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Windows 콘솔 UTF-8 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("Error: Google API 라이브러리가 설치되지 않았습니다.")
    print(
        "설치: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
    )
    sys.exit(1)

# 인증 파일 경로 (google-workspace Skill과 동일)
CREDENTIALS_DIR = Path(r"C:\claude\json")
CREDENTIALS_FILE = CREDENTIALS_DIR / "desktop_credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token_gmail.json"

# OAuth Scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


def get_credentials() -> Credentials:
    """Google OAuth 인증 처리"""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"Error: OAuth 자격증명 파일이 없습니다: {CREDENTIALS_FILE}")
                print(
                    "Google Cloud Console에서 OAuth 클라이언트 ID를 생성하고 다운로드하세요."
                )
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def extract_email_body(payload: dict) -> str:
    """이메일 본문 추출 (HTML → 텍스트)"""
    body = ""

    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="ignore"
        )
    elif "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="ignore"
                )
                break
            elif mime_type == "text/html" and part.get("body", {}).get("data"):
                html = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="ignore"
                )
                # 간단한 HTML 태그 제거
                body = re.sub(r"<[^>]+>", " ", html)
                body = re.sub(r"\s+", " ", body).strip()
            elif "parts" in part:
                # 중첩된 multipart 처리
                body = extract_email_body(part)
                if body:
                    break

    return body[:2000]  # 최대 2000자


def extract_headers(headers: list) -> dict:
    """이메일 헤더 추출"""
    result = {}
    header_names = ["From", "Subject", "Date", "To"]
    for header in headers:
        if header["name"] in header_names:
            result[header["name"].lower()] = header["value"]
    return result


def parse_date(date_str: str) -> Optional[datetime]:
    """이메일 날짜 파싱"""
    # 다양한 날짜 형식 처리
    patterns = [
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]

    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                if groups[1] in months:
                    return datetime(int(groups[2]), months[groups[1]], int(groups[0]))
                else:
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))

    return None


def calculate_hours_since(date_str: str) -> int:
    """이메일 수신 후 경과 시간 계산 (시간 단위)"""
    email_date = parse_date(date_str)
    if not email_date:
        return 0

    now = datetime.now()
    delta = now - email_date
    return int(delta.total_seconds() / 3600)


def analyze_email_for_tasks(email_data: dict) -> dict:
    """이메일에서 할일 추출 (규칙 기반)"""
    headers = email_data.get("headers", {})
    body = email_data.get("body", "")
    subject = headers.get("subject", "")

    # 할일 감지 키워드
    action_keywords = [
        "확인해 주세요",
        "검토해 주세요",
        "보내주세요",
        "회신",
        "답변",
        "please review",
        "please check",
        "action required",
        "urgent",
        "마감",
        "deadline",
        "due date",
        "until",
        "by end of",
        "요청드립니다",
        "부탁드립니다",
        "처리해 주세요",
    ]

    # 긴급도 감지 키워드
    urgent_keywords = ["긴급", "urgent", "asap", "immediately", "오늘까지", "today"]
    medium_keywords = ["이번 주", "this week", "soon", "빨리"]

    # 마감일 감지 패턴
    deadline_patterns = [
        r"마감[:\s]*(\d{1,2}[/.-]\d{1,2})",
        r"until\s+(\w+\s+\d{1,2})",
        r"by\s+(\w+\s+\d{1,2})",
        r"(\d{1,2}월\s*\d{1,2}일)",
        r"(\d{1,2}/\d{1,2})",
    ]

    # 할일 여부 확인
    combined_text = f"{subject} {body}".lower()
    has_action = any(kw.lower() in combined_text for kw in action_keywords)

    # 긴급도 판단
    priority = "low"
    if any(kw.lower() in combined_text for kw in urgent_keywords):
        priority = "high"
    elif any(kw.lower() in combined_text for kw in medium_keywords):
        priority = "medium"
    elif has_action:
        priority = "medium"

    # 마감일 추출
    deadline = None
    for pattern in deadline_patterns:
        match = re.search(pattern, combined_text)
        if match:
            deadline = match.group(1)
            break

    # 발신자 추출
    sender = headers.get("from", "Unknown")
    sender_match = re.search(r"([^<]+)", sender)
    if sender_match:
        sender = sender_match.group(1).strip()

    # 미응답 확인 (RE: 또는 Re: 포함 시)
    is_reply_needed = "re:" in subject.lower() or "답변" in combined_text

    # 경과 시간
    hours_since = calculate_hours_since(headers.get("date", ""))

    return {
        "subject": subject,
        "sender": sender,
        "date": headers.get("date", ""),
        "has_action": has_action,
        "priority": priority,
        "deadline": deadline,
        "is_reply_needed": is_reply_needed,
        "hours_since": hours_since,
        "snippet": body[:200] if body else "",
    }


def list_emails(service, query: str = "is:unread", max_results: int = 20) -> list:
    """이메일 목록 조회"""
    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )

            headers = extract_headers(detail.get("payload", {}).get("headers", []))
            body = extract_email_body(detail.get("payload", {}))

            emails.append(
                {
                    "id": msg["id"],
                    "headers": headers,
                    "body": body,
                    "snippet": detail.get("snippet", ""),
                }
            )

        return emails

    except Exception as e:
        print(f"Error: 이메일 조회 실패 - {e}")
        return []


def format_output(tasks: list) -> str:
    """결과 포맷팅"""
    if not tasks:
        return "📧 분석된 이메일이 없습니다."

    # 할일이 있는 이메일만 필터
    action_tasks = [t for t in tasks if t["has_action"]]
    unanswered = [t for t in tasks if t["is_reply_needed"] and t["hours_since"] >= 48]

    output = []

    if action_tasks:
        output.append(f"📧 이메일 할일 ({len(action_tasks)}건)")
        for task in sorted(
            action_tasks,
            key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]],
        ):
            priority_icon = {"high": "긴급", "medium": "보통", "low": "낮음"}[
                task["priority"]
            ]
            deadline_str = f" - 마감 {task['deadline']}" if task["deadline"] else ""
            output.append(f"├── [{priority_icon}] {task['subject']}{deadline_str}")
            output.append(f"│       발신: {task['sender']}")

    if unanswered:
        output.append("")
        output.append(f"⚠️ 미응답 이메일 ({len(unanswered)}건)")
        for task in unanswered:
            hours = task["hours_since"]
            output.append(f"├── {task['subject']} - {hours}시간 경과")

    return "\n".join(output) if output else "📧 할일이 있는 이메일이 없습니다."


def main():
    parser = argparse.ArgumentParser(description="Gmail 이메일 분석기")
    parser.add_argument(
        "--unread", action="store_true", default=True, help="미읽은 이메일만 분석"
    )
    parser.add_argument("--days", type=int, default=3, help="최근 N일 이메일 분석")
    parser.add_argument("--max", type=int, default=20, help="최대 분석 이메일 수")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    args = parser.parse_args()

    # 인증
    print("🔐 Gmail 인증 중...")
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    # 쿼리 구성
    query_parts = []
    if args.unread:
        query_parts.append("is:unread")

    if args.days:
        date_after = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
        query_parts.append(f"after:{date_after}")

    query = " ".join(query_parts) if query_parts else ""

    # 이메일 조회
    print(f"📧 이메일 조회 중... (쿼리: {query})")
    emails = list_emails(service, query=query, max_results=args.max)

    if not emails:
        print("📧 조회된 이메일이 없습니다.")
        return

    # 분석
    print(f"🔍 {len(emails)}개 이메일 분석 중...")
    tasks = [analyze_email_for_tasks(email) for email in emails]

    # 출력
    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        print("\n" + format_output(tasks))


if __name__ == "__main__":
    main()
