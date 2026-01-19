#!/usr/bin/env python
"""
AE-Nexrender 렌더링 워커 실행 스크립트

독립적으로 실행 가능한 렌더링 워커입니다.
Supabase render_queue를 폴링하여 작업을 처리합니다.

사용법:
    # 기본 실행
    python scripts/render_worker.py

    # 환경 지정
    python scripts/render_worker.py --env prod

    # 디버그 모드
    python scripts/render_worker.py --env dev --log-level DEBUG
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(level: str = "INFO") -> None:
    """로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_env_file(env: str) -> None:
    """환경별 .env 파일 로드"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[Warning] python-dotenv 미설치 - .env 파일 로드 생략")
        return

    # 환경별 .env 파일 경로
    env_files = [
        PROJECT_ROOT / f".env.{env}",
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / ".env",
    ]

    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            print(f"[Config] 환경 파일 로드: {env_file}")
            break


async def run_worker(
    poll_interval: int = 10,
    max_jobs: int = 0,
) -> None:
    """워커 메인 루프 실행

    Args:
        poll_interval: 폴링 간격 (초)
        max_jobs: 최대 처리 작업 수 (0=무제한)
    """
    logger = logging.getLogger(__name__)

    # 워커 모듈 임포트
    try:
        from worker.config import WorkerConfig
        from worker.job_processor import JobProcessor
        from worker.supabase_client import SupabaseQueueClient
    except ImportError as e:
        logger.error(f"워커 모듈 임포트 실패: {e}")
        logger.error("worker/ 디렉토리가 존재하는지 확인하세요.")
        return

    # 설정 로드
    try:
        config = WorkerConfig.from_env()
        logger.info(f"[Worker] 설정 로드 완료: Nexrender={config.nexrender_url}")
    except Exception as e:
        logger.error(f"설정 로드 실패: {e}")
        return

    # Supabase 클라이언트 초기화
    try:
        supabase_client = SupabaseQueueClient(
            url=config.supabase_url,
            key=config.supabase_service_key,
        )
        logger.info("[Worker] Supabase 클라이언트 초기화 완료")
    except Exception as e:
        logger.error(f"Supabase 클라이언트 초기화 실패: {e}")
        return

    # JobProcessor 초기화
    try:
        processor = JobProcessor(
            config=config,
            supabase_client=supabase_client,
        )
        logger.info("[Worker] JobProcessor 초기화 완료")
    except Exception as e:
        logger.error(f"JobProcessor 초기화 실패: {e}")
        return

    # 종료 플래그
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"[Worker] 종료 신호 수신: {sig}")
        shutdown_event.set()

    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 메인 루프
    jobs_processed = 0
    logger.info(f"[Worker] 워커 시작 (폴링 간격: {poll_interval}초)")

    while not shutdown_event.is_set():
        try:
            # 대기 작업 확인 및 처리
            job = await supabase_client.claim_pending_job()

            if job:
                logger.info(f"[Worker] 작업 처리 시작: {job['id']}")
                try:
                    await processor.process_job(job)
                    jobs_processed += 1
                    logger.info(
                        f"[Worker] 작업 완료: {job['id']} "
                        f"(총 {jobs_processed}개 처리)"
                    )
                except Exception as e:
                    logger.error(f"[Worker] 작업 처리 실패: {job['id']} - {e}")

                # 최대 작업 수 도달 확인
                if max_jobs > 0 and jobs_processed >= max_jobs:
                    logger.info(f"[Worker] 최대 작업 수 도달: {max_jobs}")
                    break
            else:
                # 대기 작업 없음 - 폴링 대기
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=poll_interval,
                    )
                except asyncio.TimeoutError:
                    pass  # 타임아웃은 정상적인 폴링 주기

        except Exception as e:
            logger.error(f"[Worker] 폴링 오류: {e}")
            # 에러 후 짧은 대기
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=5,
                )
            except asyncio.TimeoutError:
                pass

    logger.info(f"[Worker] 워커 종료 (처리된 작업: {jobs_processed}개)")


def main() -> None:
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="AE-Nexrender 렌더링 워커",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
    # 기본 실행
    python scripts/render_worker.py

    # 프로덕션 환경
    python scripts/render_worker.py --env prod

    # 디버그 모드 (짧은 폴링 간격)
    python scripts/render_worker.py --env dev --poll-interval 5 --log-level DEBUG

    # 테스트 (최대 10개 작업 후 종료)
    python scripts/render_worker.py --max-jobs 10
        """,
    )

    # 환경 설정
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="실행 환경 (기본: dev)",
    )

    # 워커 설정
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="폴링 간격 (초, 기본: 10)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=0,
        help="최대 처리 작업 수 (0=무제한, 기본: 0)",
    )

    # 로깅
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="로그 레벨",
    )

    args = parser.parse_args()

    # 환경 설정
    os.environ["ENV"] = args.env
    load_env_file(args.env)

    # 로깅 설정
    log_level = args.log_level or ("DEBUG" if args.env == "dev" else "INFO")
    setup_logging(log_level)

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║            AE-Nexrender 렌더링 워커                             ║
╠═══════════════════════════════════════════════════════════════╣
║  환경: {args.env:<10}                                          ║
║  폴링 간격: {args.poll_interval:<3}초                                       ║
║  최대 작업: {'무제한' if args.max_jobs == 0 else str(args.max_jobs) + '개':<10}                                    ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    try:
        asyncio.run(
            run_worker(
                poll_interval=args.poll_interval,
                max_jobs=args.max_jobs,
            )
        )
    except KeyboardInterrupt:
        print("\n[Worker] 워커 종료")
    except Exception as e:
        print(f"[Error] 워커 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
