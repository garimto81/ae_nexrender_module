"""
Supabase render_queue CRUD 클라이언트

기존 Supabase 스키마 (orch_render_status, orch_render_type)와 호환.
claim_render_job RPC 없이 직접 쿼리로 작업 할당.
"""

import socket
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from lib.types import RenderStatus
from .config import WorkerConfig


class SupabaseQueueClient:
    """Supabase render_queue 클라이언트 (기존 스키마 호환)"""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.client: Client = create_client(
            config.supabase_url, config.supabase_service_key
        )
        self.worker_host = socket.gethostname()

    async def claim_pending_job(self, worker_id: str) -> dict[str, Any] | None:
        """
        대기 중인 작업을 할당

        기존 스키마에 claim_render_job RPC가 없으므로
        SELECT → UPDATE 방식으로 처리.

        Args:
            worker_id: 워커 ID (TEXT)

        Returns:
            할당된 작업 또는 None (대기 작업 없음)
        """
        # 1. pending 상태의 가장 높은 우선순위 작업 조회
        response = (
            self.client.table("render_queue")
            .select("id")
            .eq("status", RenderStatus.PENDING.value)
            .order("priority", desc=False)  # 낮은 숫자 = 높은 우선순위
            .order("queued_at", desc=False)  # 오래된 것 먼저
            .limit(1)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            return None

        job_id = response.data[0]["id"]

        # 2. 작업 상태를 preparing으로 업데이트 (atomic하지 않지만 실용적)
        update_response = (
            self.client.table("render_queue")
            .update({
                "status": RenderStatus.PREPARING.value,
                "worker_id": worker_id,
                "worker_host": self.worker_host,
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", job_id)
            .eq("status", RenderStatus.PENDING.value)  # 동시성 보호
            .execute()
        )

        if update_response.data and len(update_response.data) > 0:
            return update_response.data[0]

        # 다른 워커가 먼저 가져간 경우
        return None

    async def update_job_status(
        self, job_id: str, status: str, **kwargs
    ) -> dict[str, Any]:
        """
        작업 상태 업데이트

        Args:
            job_id: 작업 ID
            status: 새 상태 (orch_render_status enum 값)
            **kwargs: 추가 업데이트 필드
                - progress (int): 진행률 (0-100)
                - current_frame (int): 현재 프레임
                - total_frames (int): 전체 프레임
                - error_message (str): 에러 메시지
                - error_details (dict): 에러 상세 (retry_count 등 포함)
                - output_path (str): 출력 파일 경로
                - output_file_size (int): 파일 크기
                - output_duration_seconds (float): 출력 영상 길이
                - render_duration_ms (int): 렌더링 소요 시간
                - completed_at (str): 완료 시각 (ISO8601)
                - metadata (dict): 추가 메타데이터 (nexrender_job_id 등)
                - worker_id (str | None): 워커 ID

        Returns:
            업데이트된 작업 레코드
        """
        update_data: dict[str, Any] = {"status": status}

        # 허용 컬럼만 필터링
        allowed_columns = {
            "progress", "current_frame", "total_frames",
            "error_message", "error_details", "error_frame",
            "output_path", "output_file_size", "output_duration_seconds",
            "render_duration_ms", "completed_at", "started_at",
            "metadata", "worker_id", "worker_host", "aerender_pid",
            "cache_hit", "cached_output_path", "estimated_completion",
        }

        for key, value in kwargs.items():
            if key in allowed_columns:
                update_data[key] = value

        response = (
            self.client.table("render_queue")
            .update(update_data)
            .eq("id", job_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]

        raise ValueError(f"작업 업데이트 실패: {job_id}")

    async def update_progress(
        self,
        job_id: str,
        progress: int,
        current_frame: int | None = None,
        nexrender_state: str | None = None,
    ) -> None:
        """
        진행률 업데이트 (간편 메서드)

        Args:
            job_id: 작업 ID
            progress: 진행률 (0-100)
            current_frame: 현재 프레임
            nexrender_state: Nexrender 상태
        """
        update_data: dict[str, Any] = {"progress": progress}

        if current_frame is not None:
            update_data["current_frame"] = current_frame

        # nexrender_state는 metadata에 저장
        if nexrender_state:
            # 기존 metadata 조회
            job = await self.get_job(job_id)
            if job:
                metadata = job.get("metadata", {}) or {}
                metadata["nexrender_state"] = nexrender_state
                update_data["metadata"] = metadata

        self.client.table("render_queue").update(update_data).eq("id", job_id).execute()

    async def set_nexrender_job_id(self, job_id: str, nexrender_job_id: str) -> None:
        """
        Nexrender Job ID 저장 (metadata에)

        Args:
            job_id: 작업 ID
            nexrender_job_id: Nexrender Job UID
        """
        job = await self.get_job(job_id)
        if job:
            metadata = job.get("metadata", {}) or {}
            metadata["nexrender_job_id"] = nexrender_job_id
            self.client.table("render_queue").update(
                {"metadata": metadata}
            ).eq("id", job_id).execute()

    async def mark_completed(
        self,
        job_id: str,
        output_path: str,
        output_file_size: int | None = None,
        render_duration_ms: int | None = None,
    ) -> dict[str, Any]:
        """
        작업 완료 처리

        Args:
            job_id: 작업 ID
            output_path: 출력 파일 경로
            output_file_size: 파일 크기
            render_duration_ms: 렌더링 소요 시간
        """
        update_data: dict[str, Any] = {
            "status": RenderStatus.COMPLETED.value,
            "progress": 100,
            "output_path": output_path,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "worker_id": None,  # 락 해제
        }

        if output_file_size is not None:
            update_data["output_file_size"] = output_file_size

        if render_duration_ms is not None:
            update_data["render_duration_ms"] = render_duration_ms

        return await self.update_job_status(job_id, RenderStatus.COMPLETED.value, **update_data)

    async def mark_failed(
        self,
        job_id: str,
        error_message: str,
        error_category: str = "unknown",
        should_retry: bool = False,
    ) -> dict[str, Any]:
        """
        작업 실패 처리

        Args:
            job_id: 작업 ID
            error_message: 에러 메시지
            error_category: 에러 카테고리 (retryable, non_retryable, unknown)
            should_retry: 재시도 여부 (True면 pending으로 복원)
        """
        # 기존 error_details 조회
        job = await self.get_job(job_id)
        error_details = {}
        if job:
            error_details = job.get("error_details", {}) or {}

        # retry_count 증가
        retry_count = error_details.get("retry_count", 0) + 1
        max_retries = error_details.get("max_retries", 3)

        error_details["retry_count"] = retry_count
        error_details["max_retries"] = max_retries
        error_details["error_category"] = error_category
        error_details["last_error_at"] = datetime.now(timezone.utc).isoformat()

        # 재시도 가능하고 한도 미달이면 pending으로
        if should_retry and retry_count < max_retries:
            return await self.update_job_status(
                job_id,
                RenderStatus.PENDING.value,
                error_message=error_message,
                error_details=error_details,
                worker_id=None,
            )

        # 최종 실패
        return await self.update_job_status(
            job_id,
            RenderStatus.FAILED.value,
            error_message=error_message,
            error_details=error_details,
            completed_at=datetime.now(timezone.utc).isoformat(),
            worker_id=None,
        )

    async def release_job(self, job_id: str) -> None:
        """
        작업 락 해제 (pending으로 복원)

        워커 크래시 시 호출하여 다른 워커가 재처리할 수 있게 함.

        Args:
            job_id: 작업 ID
        """
        # 기존 error_details 조회
        job = await self.get_job(job_id)
        error_details = {}
        if job:
            error_details = job.get("error_details", {}) or {}

        recovery_count = error_details.get("recovery_count", 0)
        error_details["recovery_count"] = recovery_count + 1
        error_details["last_recovery_at"] = datetime.now(timezone.utc).isoformat()

        # pending으로 복원
        self.client.table("render_queue").update({
            "status": RenderStatus.PENDING.value,
            "worker_id": None,
            "error_details": error_details,
        }).eq("id", job_id).execute()

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """
        작업 조회

        Args:
            job_id: 작업 ID

        Returns:
            작업 레코드 또는 None
        """
        response = (
            self.client.table("render_queue").select("*").eq("id", job_id).execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]

        return None

    async def get_pending_count(self) -> int:
        """대기 중인 작업 수 조회"""
        response = (
            self.client.table("render_queue")
            .select("id", count="exact")
            .eq("status", RenderStatus.PENDING.value)
            .execute()
        )
        return response.count or 0
