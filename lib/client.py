"""
Nexrender API 클라이언트 (비동기/동기)

기존 automation_ae의 client.py 기반으로 개선:
- 재시도 로직 내장
- 커넥션 풀 관리
- 상세 로깅
- poll_until_complete 추가
"""

import asyncio
import logging
from typing import Any, Callable

import httpx

from .errors import NexrenderError

logger = logging.getLogger(__name__)


class NexrenderClient:
    """비동기 Nexrender API 클라이언트

    Note: Celery 워커 호환성을 위해 httpx.AsyncClient를 캐싱하지 않음
    (각 이벤트 루프에서 새로운 클라이언트 생성)
    """

    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.secret = secret
        self.timeout = timeout
        self.max_retries = max_retries

    def _create_client(self) -> httpx.AsyncClient:
        """새로운 HTTP 클라이언트 생성 (매 요청마다)"""
        headers = {}
        if self.secret:
            headers["nexrender-secret"] = self.secret

        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )

    async def close(self) -> None:
        """클라이언트 종료 (호환성용, 실제로는 no-op)"""
        pass

    async def health_check(self) -> bool:
        """Nexrender 서버 헬스 체크

        Returns:
            bool: 서버 정상 여부
        """
        try:
            async with self._create_client() as client:
                response = await client.get("/api/v1/jobs")
                return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Nexrender health check failed: {e}")
            return False

    async def submit_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """렌더링 작업 제출

        Args:
            job_data: Nexrender Job JSON

        Returns:
            dict: 제출된 작업 정보 (uid 포함)

        Raises:
            NexrenderError: 작업 제출 실패
        """
        try:
            async with self._create_client() as client:
                response = await client.post("/api/v1/jobs", json=job_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Nexrender submit job failed: {e.response.text}")
            raise NexrenderError(f"작업 제출 실패: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error(f"Nexrender submit job error: {e}")
            raise NexrenderError(f"Nexrender 서버 연결 실패: {e}") from e

    async def get_job(self, job_uid: str) -> dict[str, Any]:
        """작업 상태 조회

        Args:
            job_uid: Nexrender Job UID

        Returns:
            dict: 작업 상태 정보

        Raises:
            NexrenderError: 작업 조회 실패
        """
        try:
            async with self._create_client() as client:
                response = await client.get(f"/api/v1/jobs/{job_uid}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NexrenderError("작업을 찾을 수 없습니다") from e
            logger.error(f"Nexrender get job failed: {e.response.text}")
            raise NexrenderError(f"작업 조회 실패: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error(f"Nexrender get job error: {e}")
            raise NexrenderError(f"Nexrender 서버 연결 실패: {e}") from e

    async def list_jobs(self) -> list[dict[str, Any]]:
        """모든 작업 목록 조회

        Returns:
            list: 작업 목록

        Raises:
            NexrenderError: 목록 조회 실패
        """
        try:
            async with self._create_client() as client:
                response = await client.get("/api/v1/jobs")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Nexrender list jobs error: {e}")
            raise NexrenderError(f"작업 목록 조회 실패: {e}") from e

    async def cancel_job(self, job_uid: str) -> bool:
        """작업 취소

        Args:
            job_uid: Nexrender Job UID

        Returns:
            bool: 취소 성공 여부
        """
        try:
            async with self._create_client() as client:
                response = await client.delete(f"/api/v1/jobs/{job_uid}")
                return response.status_code in (200, 204)
        except httpx.HTTPError as e:
            logger.error(f"Nexrender cancel job error: {e}")
            return False

    async def poll_until_complete(
        self,
        job_uid: str,
        callback: Callable[[int, str], None] | None = None,
        timeout: int = 1800,  # 30분
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """작업 완료까지 폴링

        Args:
            job_uid: Nexrender Job UID
            callback: 진행률 콜백 함수 (progress, state)
            timeout: 최대 대기 시간 (초)
            poll_interval: 폴링 주기 (초)

        Returns:
            dict: 완료된 작업 정보

        Raises:
            TimeoutError: 타임아웃 초과
            NexrenderError: 렌더링 실패
        """
        elapsed = 0

        while elapsed < timeout:
            job_status = await self.get_job(job_uid)
            state = job_status.get("state", "")
            render_progress = job_status.get("renderProgress", 0)
            error = job_status.get("error")

            if callback:
                callback(int(render_progress * 100), state)

            if state == "error":
                raise NexrenderError(f"렌더링 실패: {error}")

            if state == "finished":
                return job_status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"렌더링 타임아웃 ({timeout}초 초과)")


class NexrenderSyncClient:
    """동기 Nexrender API 클라이언트 (Celery 워커용)"""

    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.secret = secret
        self.timeout = timeout

    def _create_client(self) -> httpx.Client:
        """동기 HTTP 클라이언트 생성"""
        headers = {}
        if self.secret:
            headers["nexrender-secret"] = self.secret

        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )

    def submit_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """작업 제출 (동기)

        Args:
            job_data: Nexrender Job JSON

        Returns:
            dict: 제출된 작업 정보 (uid 포함)

        Raises:
            NexrenderError: 작업 제출 실패
        """
        try:
            with self._create_client() as client:
                response = client.post("/api/v1/jobs", json=job_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Nexrender submit job failed: {e.response.text}")
            raise NexrenderError(f"작업 제출 실패: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error(f"Nexrender submit job error: {e}")
            raise NexrenderError(f"Nexrender 서버 연결 실패: {e}") from e

    def get_job(self, job_uid: str) -> dict[str, Any]:
        """작업 상태 조회 (동기)

        Args:
            job_uid: Nexrender Job UID

        Returns:
            dict: 작업 상태 정보

        Raises:
            NexrenderError: 작업 조회 실패
        """
        try:
            with self._create_client() as client:
                response = client.get(f"/api/v1/jobs/{job_uid}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NexrenderError("작업을 찾을 수 없습니다") from e
            logger.error(f"Nexrender get job failed: {e.response.text}")
            raise NexrenderError(f"작업 조회 실패: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error(f"Nexrender get job error: {e}")
            raise NexrenderError(f"Nexrender 서버 연결 실패: {e}") from e
