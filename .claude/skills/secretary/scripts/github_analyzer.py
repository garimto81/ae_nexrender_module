#!/usr/bin/env python3
"""
GitHub Analyzer - 최근 활동 분석

Usage:
    python github_analyzer.py [--days N] [--user USERNAME]

Options:
    --days N        최근 N일 활동 분석 (기본: 5일)
    --user NAME     특정 사용자 분석 (기본: 인증된 사용자)
    --repos         레포지토리 목록만 조회

Output:
    GitHub 활동 현황 및 주의 필요 항목
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Windows 콘솔 UTF-8 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("Error: httpx 라이브러리가 설치되지 않았습니다.")
    print("설치: pip install httpx")
    sys.exit(1)

# GitHub 토큰 경로
TOKEN_FILE = Path(r"C:\claude\json\github_token.txt")
BASE_URL = "https://api.github.com"


def get_github_token() -> str:
    """GitHub 토큰 로드"""
    # 환경 변수 우선
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # 파일에서 로드
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()

    print("Error: GitHub 토큰이 설정되지 않았습니다.")
    print(f"환경 변수 GITHUB_TOKEN을 설정하거나 {TOKEN_FILE}에 토큰을 저장하세요.")
    sys.exit(1)


def get_headers(token: str) -> dict:
    """API 요청 헤더"""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def api_get(endpoint: str, token: str, params: dict = None) -> Optional[dict | list]:
    """GitHub API GET 요청"""
    url = f"{BASE_URL}{endpoint}"
    headers = get_headers(token)

    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"Warning: Rate limit exceeded or forbidden - {endpoint}")
                return None
            elif response.status_code == 404:
                return None
            else:
                print(f"Error: API 요청 실패 - {response.status_code} {endpoint}")
                return None

    except Exception as e:
        print(f"Error: API 요청 오류 - {e}")
        return None


def get_user_repos(token: str, sort: str = "pushed", per_page: int = 30) -> list:
    """사용자 레포지토리 목록"""
    repos = api_get("/user/repos", token, params={"sort": sort, "per_page": per_page})
    return repos if repos else []


def get_repo_commits(
    token: str, owner: str, repo: str, since: str, per_page: int = 50
) -> list:
    """레포지토리 커밋 목록"""
    commits = api_get(
        f"/repos/{owner}/{repo}/commits",
        token,
        params={"since": since, "per_page": per_page},
    )
    return commits if commits else []


def get_repo_issues(
    token: str, owner: str, repo: str, since: str, state: str = "all"
) -> list:
    """레포지토리 이슈 목록"""
    issues = api_get(
        f"/repos/{owner}/{repo}/issues",
        token,
        params={"since": since, "state": state, "per_page": 50},
    )
    return issues if issues else []


def get_repo_prs(token: str, owner: str, repo: str, state: str = "open") -> list:
    """레포지토리 PR 목록"""
    prs = api_get(
        f"/repos/{owner}/{repo}/pulls", token, params={"state": state, "per_page": 30}
    )
    return prs if prs else []


def days_since(date_str: str) -> int:
    """날짜 문자열로부터 경과 일수 계산"""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        return (now - dt).days
    except:
        return 0


def analyze_activity(token: str, days: int = 5) -> dict:
    """GitHub 활동 분석"""
    since = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
    since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 레포지토리 목록 조회
    print("📦 레포지토리 목록 조회 중...")
    repos = get_user_repos(token)

    if not repos:
        return {
            "active_repos": [],
            "attention_needed": [],
            "summary": {"total_commits": 0, "total_issues": 0, "total_prs": 0},
        }

    result = {
        "active_repos": [],
        "attention_needed": [],
        "summary": {"total_commits": 0, "total_issues": 0, "total_prs": 0},
    }

    # 최근 푸시가 있는 레포만 분석
    for repo in repos:
        pushed_at = repo.get("pushed_at", "")
        if not pushed_at:
            continue

        # 최근 활동이 있는 레포만 분석
        pushed_days = days_since(pushed_at)
        if pushed_days > days:
            continue

        full_name = repo["full_name"]
        owner, name = full_name.split("/")

        print(f"  🔍 {full_name} 분석 중...")

        # 커밋 조회
        commits = get_repo_commits(token, owner, name, since)
        commit_count = len(commits)

        # 이슈 조회 (PR 제외)
        issues = get_repo_issues(token, owner, name, since)
        # PR은 is pull_request 필드가 있음
        pure_issues = [i for i in issues if "pull_request" not in i]
        issue_count = len(pure_issues)

        # PR 조회
        prs = get_repo_prs(token, owner, name)
        pr_count = len(prs)

        # 활성 레포 기록
        if commit_count > 0 or issue_count > 0 or pr_count > 0:
            result["active_repos"].append(
                {
                    "name": name,
                    "full_name": full_name,
                    "commits": commit_count,
                    "issues": issue_count,
                    "prs": pr_count,
                    "pushed_at": pushed_at,
                }
            )

        # 주의 필요 항목 분석
        for pr in prs:
            created_at = pr.get("created_at", "")
            pr_days = days_since(created_at)

            # PR 리뷰 대기 3일 이상
            if pr_days >= 3:
                result["attention_needed"].append(
                    {
                        "type": "pr",
                        "repo": name,
                        "title": pr.get("title", ""),
                        "number": pr.get("number", 0),
                        "days": pr_days,
                        "reason": f"리뷰 대기 {pr_days}일",
                        "url": pr.get("html_url", ""),
                    }
                )

        for issue in pure_issues:
            updated_at = issue.get("updated_at", "")
            issue_days = days_since(updated_at)

            # 이슈 응답 없음 4일 이상
            if issue_days >= 4 and issue.get("state") == "open":
                result["attention_needed"].append(
                    {
                        "type": "issue",
                        "repo": name,
                        "title": issue.get("title", ""),
                        "number": issue.get("number", 0),
                        "days": issue_days,
                        "reason": f"응답 없음 {issue_days}일",
                        "url": issue.get("html_url", ""),
                    }
                )

        # 통계 업데이트
        result["summary"]["total_commits"] += commit_count
        result["summary"]["total_issues"] += issue_count
        result["summary"]["total_prs"] += pr_count

    # 활성 레포를 커밋 수 기준 정렬
    result["active_repos"].sort(key=lambda x: x["commits"], reverse=True)

    return result


def format_output(data: dict, days: int = 5) -> str:
    """결과 포맷팅"""
    output = [f"💻 GitHub 업무 현황 (최근 {days}일)"]

    # 활성 프로젝트
    active_repos = data.get("active_repos", [])
    if active_repos:
        output.append("")
        output.append(f"🔥 활발한 프로젝트 ({len(active_repos)}개)")
        for repo in active_repos[:10]:  # 최대 10개
            output.append(
                f"├── {repo['full_name']}: {repo['commits']} commits, {repo['issues']} issues, {repo['prs']} PRs"
            )

    # 주의 필요
    attention = data.get("attention_needed", [])
    if attention:
        output.append("")
        output.append(f"⚠️ 주의 필요 ({len(attention)}건)")
        for item in attention:
            icon = "🔀" if item["type"] == "pr" else "🐛"
            output.append(
                f"├── {icon} #{item['number']} ({item['repo']}): {item['reason']}"
            )
            output.append(f"│   {item['title'][:50]}")

    # 요약
    summary = data.get("summary", {})
    output.append("")
    output.append("📊 요약")
    output.append(f"├── 총 커밋: {summary.get('total_commits', 0)}")
    output.append(f"├── 활성 이슈: {summary.get('total_issues', 0)}")
    output.append(f"└── 오픈 PR: {summary.get('total_prs', 0)}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="GitHub 활동 분석기")
    parser.add_argument("--days", type=int, default=5, help="최근 N일 활동 분석")
    parser.add_argument("--repos", action="store_true", help="레포지토리 목록만 조회")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    args = parser.parse_args()

    # 토큰 로드
    print("🔐 GitHub 인증 중...")
    token = get_github_token()

    if args.repos:
        # 레포 목록만
        repos = get_user_repos(token)
        if args.json:
            print(json.dumps(repos, ensure_ascii=False, indent=2))
        else:
            print(f"\n📦 레포지토리 ({len(repos)}개)")
            for repo in repos:
                print(f"├── {repo['full_name']} (⭐ {repo.get('stargazers_count', 0)})")
        return

    # 전체 분석
    print(f"🔍 최근 {args.days}일 활동 분석 중...")
    data = analyze_activity(token, args.days)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("\n" + format_output(data, args.days))


if __name__ == "__main__":
    main()
