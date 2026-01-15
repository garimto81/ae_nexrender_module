"""
헬스체크 HTTP 서버

워커 상태 모니터링을 위한 간단한 HTTP 서버.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from .main import Worker

logger = logging.getLogger(__name__)


class HealthServer:
    """헬스체크 HTTP 서버

    aiohttp를 사용하여 워커 상태를 노출하는 간단한 HTTP 서버입니다.
    """

    def __init__(self, worker: "Worker"):
        """
        Args:
            worker: Worker 인스턴스 (상태 참조용)
        """
        self.worker = worker
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.started_at = datetime.now(timezone.utc)

        # 라우트 등록
        self.app.router.add_get("/health", self._health_handler)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """GET /health 엔드포인트 핸들러

        Returns:
            JSON 응답:
                {
                    "status": "ok",
                    "worker_id": "uuid",
                    "running": true,
                    "current_job_id": "uuid" | null,
                    "uptime_seconds": 1234
                }
        """
        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()

        return web.json_response(
            {
                "status": "ok",
                "worker_id": str(self.worker.worker_id),
                "running": self.worker.running,
                "current_job_id": self.worker.current_job_id,
                "uptime_seconds": int(uptime),
            }
        )

    async def start(self) -> None:
        """헬스 서버 시작

        워커 시작 시 호출됩니다.
        """
        port = self.worker.config.health_port

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "0.0.0.0", port)
        await self.site.start()

        logger.info(f"[Health] 헬스 서버 시작: http://0.0.0.0:{port}/health")

    async def stop(self) -> None:
        """헬스 서버 종료

        워커 종료 시 호출됩니다.
        """
        if self.site:
            await self.site.stop()
            self.site = None

        if self.runner:
            await self.runner.cleanup()
            self.runner = None

        logger.info("[Health] 헬스 서버 종료 완료")
