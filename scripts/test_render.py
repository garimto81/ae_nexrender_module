"""
단일 렌더링 테스트 CLI

샘플 GFX 데이터로 Nexrender Job을 생성하고 렌더링을 테스트합니다.

사용법:
    # 샘플 데이터로 테스트
    python scripts/test_render.py --sample

    # 특정 컴포지션으로 테스트
    python scripts/test_render.py --composition "1-Hand-for-hand play is currently in progress"

    # Job JSON만 생성 (렌더링 안함)
    python scripts/test_render.py --sample --dry-run

    # 환경변수 커스텀 설정
    python scripts/test_render.py --sample --nexrender-url http://localhost:3000
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lib.client import NexrenderClient
from lib.job_builder import JobConfig, NexrenderJobBuilder
from tests.sample_data import SAMPLE_COMPOSITIONS, generate_sample_gfx_data


def parse_args():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="단일 렌더링 테스트 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 컴포지션 선택
    parser.add_argument(
        "--composition",
        "-c",
        type=str,
        choices=SAMPLE_COMPOSITIONS,
        help="테스트할 컴포지션 이름",
    )

    parser.add_argument(
        "--sample",
        "-s",
        action="store_true",
        help="첫 번째 샘플 컴포지션 사용",
    )

    # 출력 설정
    parser.add_argument(
        "--output-format",
        type=str,
        default="mp4",
        choices=["mp4", "mov", "mov_alpha", "png_sequence"],
        help="출력 포맷 (기본: mp4)",
    )

    parser.add_argument(
        "--output-filename",
        type=str,
        help="출력 파일명 (기본: test_render_TIMESTAMP)",
    )

    # Nexrender 연동 설정
    parser.add_argument(
        "--nexrender-url",
        type=str,
        default=os.getenv("NEXRENDER_URL", "http://localhost:3000"),
        help="Nexrender 서버 URL (기본: NEXRENDER_URL 환경변수)",
    )

    parser.add_argument(
        "--nexrender-secret",
        type=str,
        default=os.getenv("NEXRENDER_SECRET"),
        help="Nexrender API Secret (기본: NEXRENDER_SECRET 환경변수)",
    )

    # 경로 설정
    parser.add_argument(
        "--aep-path",
        type=str,
        default="C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep",
        help="AEP 프로젝트 경로 (기본: CyprusDesign.aep)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.getenv("OUTPUT_DIR_HOST", "D:/output"),
        help="출력 디렉토리 (기본: OUTPUT_DIR_HOST 환경변수)",
    )

    # 실행 모드
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Job JSON만 생성하고 렌더링하지 않음",
    )

    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="작업 제출 후 진행률 폴링 안함 (빠른 테스트용)",
    )

    return parser.parse_args()


async def test_render(args):
    """렌더링 테스트 실행

    Args:
        args: argparse 인자
    """
    # 컴포지션 선택
    if args.sample:
        composition_name = SAMPLE_COMPOSITIONS[0]
    elif args.composition:
        composition_name = args.composition
    else:
        print("Error: --sample 또는 --composition 중 하나를 지정해야 합니다.")
        sys.exit(1)

    print(f"[Test Render] 컴포지션: {composition_name}")

    # 1. 샘플 GFX 데이터 생성
    try:
        gfx_data = generate_sample_gfx_data(composition_name)
        print(f"[Test Render] GFX 데이터 생성 완료")
        print(f"  - Slots: {len(gfx_data['slots'])}")
        print(f"  - Single Fields: {list(gfx_data['single_fields'].keys())}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # 2. Job Config 생성
    job_config = JobConfig(
        aep_project_path=args.aep_path,
        composition_name=composition_name,
        output_format=args.output_format,
        output_dir=args.output_dir,
        output_filename=args.output_filename or f"test_render_{composition_name[:20]}",
    )

    # 3. Nexrender Job JSON 생성
    builder = NexrenderJobBuilder(job_config)
    job_id = "test_" + str(hash(composition_name))[:8]
    nexrender_job_data = builder.build_from_gfx_data(
        gfx_data=gfx_data,
        job_id=job_id,
    )

    print(f"\n[Test Render] Nexrender Job JSON 생성 완료")
    print(f"  - Job ID: {job_id}")
    print(f"  - Template: {nexrender_job_data['template']['src']}")
    print(f"  - Composition: {nexrender_job_data['template']['composition']}")
    print(f"  - Assets: {len(nexrender_job_data['assets'])}개")

    # Job JSON 출력
    print("\n" + "=" * 80)
    print("Nexrender Job JSON:")
    print("=" * 80)
    print(json.dumps(nexrender_job_data, indent=2, ensure_ascii=False))
    print("=" * 80)

    # Dry-run 모드: 여기서 종료
    if args.dry_run:
        print("\n[Test Render] Dry-run 모드: 렌더링하지 않고 종료")
        return

    # 4. Nexrender 클라이언트 생성
    client = NexrenderClient(
        base_url=args.nexrender_url,
        secret=args.nexrender_secret,
    )

    # 5. Nexrender 서버 헬스 체크
    print(f"\n[Test Render] Nexrender 서버 연결 확인: {args.nexrender_url}")
    is_healthy = await client.health_check()
    if not is_healthy:
        print(f"Error: Nexrender 서버 연결 실패: {args.nexrender_url}")
        print("  - Nexrender 서버가 실행 중인지 확인하세요.")
        print("  - URL이 올바른지 확인하세요.")
        sys.exit(1)
    print(f"[Test Render] Nexrender 서버 정상")

    # 6. 작업 제출
    print(f"\n[Test Render] 작업 제출 중...")
    try:
        response = await client.submit_job(nexrender_job_data)
        nexrender_job_uid = response.get("uid")
        print(f"[Test Render] 작업 제출 완료: UID={nexrender_job_uid}")
    except Exception as e:
        print(f"Error: 작업 제출 실패: {e}")
        sys.exit(1)

    # 7. 진행률 폴링 (선택)
    if args.no_poll:
        print(f"\n[Test Render] --no-poll 옵션: 폴링 건너뜀")
        print(f"  - 작업 UID: {nexrender_job_uid}")
        print(f"  - 수동 조회: curl {args.nexrender_url}/api/v1/jobs/{nexrender_job_uid}")
        return

    print(f"\n[Test Render] 진행률 폴링 시작...")

    def progress_callback(progress: int, state: str):
        """진행률 콜백"""
        print(f"  [{state.upper()}] Progress: {progress}%")

    try:
        final_status = await client.poll_until_complete(
            job_uid=nexrender_job_uid,
            callback=progress_callback,
            timeout=1800,  # 30분
            poll_interval=5,
        )
        print(f"\n[Test Render] 렌더링 완료!")
        print(f"  - 최종 상태: {final_status.get('state')}")
        print(f"  - 출력 파일: {job_config.output_dir}/{job_config.output_filename}.{job_config.output_format}")
    except TimeoutError:
        print(f"\nError: 렌더링 타임아웃 (30분 초과)")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: 렌더링 실패: {e}")
        sys.exit(1)


def main():
    """메인 엔트리포인트"""
    args = parse_args()

    # 비동기 실행
    asyncio.run(test_render(args))


if __name__ == "__main__":
    main()
