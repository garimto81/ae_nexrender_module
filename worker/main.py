"""
AE-Nexrender 워커 메인 엔트리포인트

Celery 대신 폴링 기반 비동기 워커:
- Supabase render_queue 폴링
- 적응형 폴링 주기
- 우아한 종료 처리
"""

import asyncio
import logging
import signal
import socket
import uuid
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from .config import WorkerConfig
from .health import HealthServer
from .job_processor import JobProcessor
from .supabase_client import SupabaseQueueClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class Worker:
    """AE-Nexrender 워커 (기존 스키마 호환)

    Supabase render_queue를 폴링하여 대기 작업을 처리하는 비동기 워커입니다.
    worker_id는 TEXT 타입으로 저장됩니다 (기존 스키마 호환).
    """

    def __init__(self, config: WorkerConfig):
        """
        Args:
            config: 워커 설정
        """
        self.config = config
        # worker_id는 TEXT 타입 (기존 스키마 호환)
        # 형식: hostname-uuid (식별 용이)
        hostname = socket.gethostname()
        self.worker_id = f"{hostname}-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.current_job_id: str | None = None

        self.supabase = SupabaseQueueClient(config)
        self.processor = JobProcessor(config, self.supabase)
        self.health_server = HealthServer(self)

        logger.info(f"[Worker] 워커 초기화 완료: ID={self.worker_id}")

    async def start(self) -> None:
        """워커 시작

        시그널 핸들러 등록, 헬스 서버 시작, 폴링 루프 시작.
        """
        logger.info(f"[Worker] 워커 시작: ID={self.worker_id}")
        self.running = True

        # 시그널 핸들러 등록 (Windows 호환)
        # Windows는 asyncio signal handler를 지원하지 않으므로
        # signal.signal() 사용
        import sys

        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.shutdown())
                )
        else:
            # Windows: signal.signal() 사용 (SIGTERM은 Windows에서 지원 안 함)
            signal.signal(
                signal.SIGINT, lambda s, f: asyncio.create_task(self.shutdown())
            )

        # 헬스 서버 시작
        await self.health_server.start()

        # 메인 폴링 루프
        await self._polling_loop()

    async def _polling_loop(self) -> None:
        """적응형 폴링 루프

        - 빈 폴링 10회 초과 시 idle 모드 (30초 주기)
        - 작업 있으면 busy 모드 (5초 주기)
        - 에러 발생 시 60초 주기
        """
        empty_poll_count = 0
        poll_interval = self.config.poll_interval_default

        logger.info("[Worker] 폴링 루프 시작")

        while self.running:
            try:
                # 1. 대기 작업 조회 및 할당 (claim_render_job RPC)
                job = await self.supabase.claim_pending_job(self.worker_id)

                if job:
                    # 작업 있음 → busy 모드
                    empty_poll_count = 0
                    poll_interval = self.config.poll_interval_busy

                    job_id = job["id"]
                    logger.info(
                        f"[Worker] 작업 할당됨: Job {job_id}, "
                        f"composition={job.get('aep_comp_name', 'N/A')}"
                    )

                    self.current_job_id = job_id

                    # 작업 처리
                    try:
                        await self.processor.process(job)
                    except Exception as e:
                        logger.error(
                            f"[Worker] 작업 처리 중 에러: Job {job_id}, Error: {e}"
                        )
                    finally:
                        self.current_job_id = None

                else:
                    # 작업 없음 → empty_poll_count 증가
                    empty_poll_count += 1

                    if empty_poll_count > self.config.empty_poll_threshold:
                        # idle 모드로 전환
                        if poll_interval != self.config.poll_interval_idle:
                            poll_interval = self.config.poll_interval_idle
                            logger.info(
                                f"[Worker] Idle 모드 전환 (빈 폴링 {empty_poll_count}회)"
                            )

            except Exception as e:
                logger.error(f"[Worker] 폴링 루프 에러: {e}", exc_info=True)
                poll_interval = self.config.poll_interval_error  # 에러 모드 60초

            # 폴링 주기만큼 대기
            await asyncio.sleep(poll_interval)

        logger.info("[Worker] 폴링 루프 종료")

    async def shutdown(self) -> None:
        """우아한 종료

        현재 작업이 있으면 상태를 복원하고, 헬스 서버를 종료합니다.
        """
        logger.info("[Worker] 종료 신호 수신, 우아한 종료 시작...")
        self.running = False

        # 현재 작업이 있으면 락 해제 (다른 워커가 재처리할 수 있도록)
        if self.current_job_id:
            logger.info(f"[Worker] 현재 작업 릴리즈: Job {self.current_job_id}")
            try:
                await self.supabase.release_job(self.current_job_id)
            except Exception as e:
                logger.error(f"[Worker] 작업 릴리즈 실패: {e}")

        # 헬스 서버 종료
        await self.health_server.stop()

        logger.info("[Worker] 종료 완료")


# ============================================================================
# 엔트리포인트
# ============================================================================


def run() -> None:
    """워커 실행 (엔트리포인트)

    환경변수에서 설정을 로드하고 워커를 시작합니다.
    """
    logger.info("=" * 60)
    logger.info("AE-Nexrender Worker v2.0")
    logger.info("=" * 60)

    # 설정 로드
    config = WorkerConfig.from_env()

    # 설정 검증
    if not config.supabase_url or not config.supabase_service_key:
        logger.error("환경변수 누락: SUPABASE_URL, SUPABASE_SERVICE_KEY 필수")
        raise ValueError("Supabase 설정 누락")

    logger.info(f"Supabase URL: {config.supabase_url}")
    logger.info(f"Nexrender URL: {config.nexrender_url}")
    logger.info(f"Output Dir: {config.output_dir}")
    logger.info(f"Health Port: {config.health_port}")

    # 워커 시작
    worker = Worker(config)
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("[Worker] KeyboardInterrupt 수신, 종료 중...")
    except Exception as e:
        logger.error(f"[Worker] 예상치 못한 에러: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run()
