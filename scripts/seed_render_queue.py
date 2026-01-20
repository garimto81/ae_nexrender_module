"""
Supabase render_queue 시딩 스크립트

테스트용 렌더링 작업을 render_queue 테이블에 삽입합니다.

사용법:
    # 5개 샘플 작업 생성
    python scripts/seed_render_queue.py --count 5

    # 특정 컴포지션으로 작업 생성
    python scripts/seed_render_queue.py --composition "1-Hand-for-hand play is currently in progress"

    # 모든 컴포지션 타입 생성
    python scripts/seed_render_queue.py --all

    # 환경변수 커스텀 설정
    python scripts/seed_render_queue.py --count 3 --supabase-url https://xxx.supabase.co

전제조건:
    - .env 파일에 SUPABASE_URL, SUPABASE_SERVICE_KEY 설정
    - Supabase render_queue 테이블 생성 완료
"""

import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from supabase import Client, create_client
from tests.sample_data import (
    SAMPLE_COMPOSITIONS,
    generate_batch_render_requests,
    generate_sample_render_request,
)


def parse_args():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Supabase render_queue 시딩 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 작업 생성 모드
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--count",
        "-n",
        type=int,
        help="생성할 작업 개수 (랜덤 컴포지션)",
    )

    group.add_argument(
        "--composition",
        "-c",
        type=str,
        choices=SAMPLE_COMPOSITIONS,
        help="특정 컴포지션으로 작업 생성",
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="모든 컴포지션 타입 생성 (5개)",
    )

    # 출력 설정
    # [필수] 기본값: mov_alpha (투명 배경)
    parser.add_argument(
        "--output-format",
        type=str,
        default="mov_alpha",
        choices=["mov_alpha", "mov", "mp4", "png_sequence"],
        help="출력 포맷 (기본: mov_alpha - 투명 배경 필수)",
    )

    parser.add_argument(
        "--priority",
        type=int,
        default=5,
        choices=range(1, 11),
        metavar="1-10",
        help="우선순위 (기본: 5)",
    )

    # Supabase 연동 설정
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=os.getenv("SUPABASE_URL"),
        help="Supabase URL (기본: SUPABASE_URL 환경변수)",
    )

    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_SERVICE_KEY"),
        help="Supabase Service Key (기본: SUPABASE_SERVICE_KEY 환경변수)",
    )

    # 출력 옵션
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 출력 (생성된 작업의 GFX 데이터 포함)",
    )

    return parser.parse_args()


def validate_env(args):
    """환경변수 검증"""
    if not args.supabase_url:
        print("Error: SUPABASE_URL 환경변수가 설정되지 않았습니다.")
        print("  - .env 파일에 SUPABASE_URL=https://xxx.supabase.co 추가")
        print("  - 또는 --supabase-url 옵션 사용")
        sys.exit(1)

    if not args.supabase_key:
        print("Error: SUPABASE_SERVICE_KEY 환경변수가 설정되지 않았습니다.")
        print("  - .env 파일에 SUPABASE_SERVICE_KEY=eyJxxx 추가")
        print("  - 또는 --supabase-key 옵션 사용")
        sys.exit(1)


def create_supabase_client(url: str, key: str) -> Client:
    """Supabase 클라이언트 생성

    Args:
        url: Supabase URL
        key: Supabase Service Key

    Returns:
        Supabase 클라이언트
    """
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"Error: Supabase 클라이언트 생성 실패: {e}")
        sys.exit(1)


def seed_render_queue(args):
    """render_queue 시딩 실행

    Args:
        args: argparse 인자
    """
    # 1. 환경변수 검증
    validate_env(args)

    # 2. Supabase 클라이언트 생성
    print(f"[Seed] Supabase 연결 중: {args.supabase_url[:30]}...")
    client = create_supabase_client(args.supabase_url, args.supabase_key)

    # 3. 작업 생성
    requests = []

    if args.count:
        print(f"[Seed] {args.count}개 랜덤 작업 생성 중...")
        requests = generate_batch_render_requests(count=args.count)
        # 우선순위 및 출력 포맷 적용
        for req in requests:
            req["output_format"] = args.output_format
            req["priority"] = args.priority

    elif args.composition:
        print(f"[Seed] 컴포지션 '{args.composition}' 작업 생성 중...")
        req = generate_sample_render_request(
            composition_name=args.composition,
            output_format=args.output_format,
            priority=args.priority,
        )
        requests = [req]

    elif args.all:
        print(
            f"[Seed] 모든 컴포지션 타입 작업 생성 중 ({len(SAMPLE_COMPOSITIONS)}개)..."
        )
        for comp_name in SAMPLE_COMPOSITIONS:
            req = generate_sample_render_request(
                composition_name=comp_name,
                output_format=args.output_format,
                priority=args.priority,
            )
            requests.append(req)

    print(f"[Seed] 생성된 작업: {len(requests)}개")

    # 4. render_queue 테이블에 삽입
    print("\n[Seed] Supabase render_queue 삽입 중...")

    inserted_count = 0
    failed_count = 0

    for i, req in enumerate(requests, 1):
        try:
            # Supabase INSERT
            response = client.table("render_queue").insert(req).execute()

            if response.data:
                inserted_count += 1
                job = response.data[0]
                print(
                    f"  [{i}/{len(requests)}] 삽입 성공: {job['id'][:8]}... ({job['composition_name'][:30]}...)"
                )

                # Verbose 모드: GFX 데이터 출력
                if args.verbose:
                    print("    GFX Data:")
                    print(f"      - Slots: {len(job['gfx_data']['slots'])}")
                    print(
                        f"      - Single Fields: {list(job['gfx_data']['single_fields'].keys())}"
                    )
            else:
                failed_count += 1
                print(f"  [{i}/{len(requests)}] 삽입 실패: 응답 데이터 없음")

        except Exception as e:
            failed_count += 1
            print(f"  [{i}/{len(requests)}] 삽입 실패: {e}")

    # 5. 결과 출력
    print("\n[Seed] 완료!")
    print(f"  - 삽입 성공: {inserted_count}개")
    print(f"  - 삽입 실패: {failed_count}개")

    if inserted_count > 0:
        print("\n[Seed] 작업 확인:")
        print(f"  - Supabase 대시보드: {args.supabase_url}/project/_/editor")
        print("  - 테이블: render_queue")
        print("  - 상태: pending")

        # 첫 번째 작업 ID 출력 (테스트용)
        first_job_id = requests[0]["id"]
        print("\n[Seed] 첫 번째 작업 ID (테스트용):")
        print(f"  {first_job_id}")


def main():
    """메인 엔트리포인트"""
    args = parse_args()

    # 시딩 실행
    seed_render_queue(args)


if __name__ == "__main__":
    main()
