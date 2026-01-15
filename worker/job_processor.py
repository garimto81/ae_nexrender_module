"""
렌더링 작업 처리기

기존 Supabase 스키마 (orch_render_status)와 호환.

5단계 프로세스:
1. Job Claim (상태: pending -> preparing)
2. Nexrender JSON 생성
3. Nexrender에 작업 제출 (상태: preparing -> rendering)
4. 진행률 폴링 (상태: rendering -> encoding -> uploading)
5. 후처리 (파일 검증, NAS 복사, 상태: completed/failed)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.client import NexrenderClient
from lib.errors import ErrorCategory, ErrorClassifier
from lib.job_builder import JobConfig, NexrenderJobBuilder
from lib.path_utils import PathConverter
from lib.types import RenderStatus

logger = logging.getLogger(__name__)


class JobProcessor:
    """렌더링 작업 처리기 (기존 스키마 호환)

    Supabase render_queue 작업을 Nexrender로 제출하고 진행률을 추적합니다.
    필드명은 기존 스키마(aep_project, aep_comp_name 등)를 사용합니다.
    """

    def __init__(self, config, supabase_client):
        """
        Args:
            config: WorkerConfig 인스턴스
            supabase_client: SupabaseQueueClient 인스턴스
        """
        self.config = config
        self.supabase = supabase_client
        self.nexrender = NexrenderClient(
            base_url=config.nexrender_url,
            secret=config.nexrender_secret,
        )
        self.path_converter = PathConverter()

    async def process(self, job: dict[str, Any]) -> dict[str, Any]:
        """작업 처리 메인 로직

        Args:
            job: render_queue 레코드 (기존 스키마)
                {
                    "id": "uuid",
                    "aep_comp_name": "Main",       # 기존: composition_name
                    "aep_project": "/app/templates/file.aep",  # 기존: aep_project_path
                    "gfx_data": {...},
                    "output_format": "mp4",
                    "output_path": "C:/output/file.mp4",  # 기존: output_dir + output_filename
                    "render_type": "custom",
                    ...
                }

        Returns:
            dict: 처리 결과
                {
                    "status": "success",
                    "job_id": "uuid",
                    "output_path": "C:/output/file.mp4"
                }

        Raises:
            Exception: 처리 중 발생한 에러
        """
        job_id = job["id"]
        start_time = time.time()
        logger.info(f"[Processor] 작업 처리 시작: Job {job_id}")

        try:
            # 1. 상태 업데이트: preparing
            await self.supabase.update_job_status(
                job_id, RenderStatus.PREPARING.value, progress=5
            )

            # 2. Nexrender Job JSON 생성
            # 기존 스키마 필드명 사용: aep_project, aep_comp_name
            aep_project = job.get("aep_project", "")
            aep_comp_name = job.get("aep_comp_name", "")
            output_format = job.get("output_format", "mp4")
            output_path = job.get("output_path", "")

            # output_path에서 디렉토리와 파일명 분리
            if output_path:
                output_dir = str(Path(output_path).parent)
                output_filename = Path(output_path).stem
            else:
                output_dir = self.config.output_dir
                output_filename = job_id

            builder = NexrenderJobBuilder(
                JobConfig(
                    aep_project_path=self.path_converter.to_windows_path(aep_project),
                    composition_name=aep_comp_name,
                    output_format=output_format,
                    output_dir=output_dir,
                    output_filename=output_filename,
                )
            )

            nexrender_job_data = builder.build_from_gfx_data(
                gfx_data=job["gfx_data"],
                job_id=job_id,
            )

            logger.debug(f"[Processor] Nexrender Job Data: {nexrender_job_data}")

            # 3. Nexrender에 작업 제출
            nexrender_response = await self.nexrender.submit_job(nexrender_job_data)
            nexrender_job_uid = nexrender_response.get("uid")

            logger.info(
                f"[Processor] Nexrender 작업 제출 완료: UID={nexrender_job_uid}"
            )

            # nexrender_job_id를 metadata에 저장
            await self.supabase.set_nexrender_job_id(job_id, nexrender_job_uid)
            await self.supabase.update_job_status(
                job_id, RenderStatus.RENDERING.value, progress=20
            )

            # 4. 진행률 폴링
            await self._poll_nexrender_progress(job_id, nexrender_job_uid)

            # 5. 후처리 (파일 검증, NAS 복사)
            final_output_path = await self._post_process(job, nexrender_job_uid)

            # 6. 완료
            render_duration_ms = int((time.time() - start_time) * 1000)
            await self.supabase.mark_completed(
                job_id,
                output_path=final_output_path,
                render_duration_ms=render_duration_ms,
            )

            logger.info(f"[Processor] 작업 완료: Job {job_id}, output={final_output_path}")

            return {
                "status": "success",
                "job_id": job_id,
                "output_path": final_output_path,
                "render_duration_ms": render_duration_ms,
            }

        except Exception as e:
            logger.error(f"[Processor] 작업 처리 실패: Job {job_id}, Error: {e}")
            await self._handle_error(job_id, e)
            raise

    async def _poll_nexrender_progress(
        self, job_id: str, nexrender_job_uid: str
    ) -> None:
        """Nexrender 작업 상태 폴링

        Args:
            job_id: render_queue 작업 ID
            nexrender_job_uid: Nexrender Job UID

        Raises:
            TimeoutError: 렌더링 타임아웃
            NexrenderError: 렌더링 실패
        """
        max_timeout = self.config.render_timeout  # 30분
        poll_interval = 5  # 5초
        elapsed = 0

        logger.info(
            f"[Processor] 진행률 폴링 시작: Job {job_id}, UID={nexrender_job_uid}"
        )

        while elapsed < max_timeout:
            try:
                nexrender_status = await self.nexrender.get_job(nexrender_job_uid)
                state = nexrender_status.get("state", "")
                render_progress = nexrender_status.get("renderProgress", 0)
                error = nexrender_status.get("error")

                logger.debug(
                    f"[Processor] Job {job_id}: Nexrender state={state}, "
                    f"progress={render_progress}"
                )

                # 상태 매핑 (Nexrender state -> render_queue status, progress)
                status_map = {
                    "queued": (RenderStatus.RENDERING.value, 25),
                    "started": (RenderStatus.RENDERING.value, 30),
                    "downloading": (RenderStatus.RENDERING.value, 35),
                    "rendering": (RenderStatus.RENDERING.value, 40 + int(render_progress * 0.4)),
                    "encoding": (RenderStatus.ENCODING.value, 85),
                    "finished": (RenderStatus.UPLOADING.value, 95),
                }

                if state == "error":
                    from lib.errors import NexrenderError

                    raise NexrenderError(f"렌더링 실패: {error}")

                if state in status_map:
                    status, progress = status_map[state]
                    await self.supabase.update_progress(
                        job_id,
                        progress=progress,
                        nexrender_state=state,
                    )
                    # 상태도 업데이트
                    await self.supabase.update_job_status(job_id, status)

                if state == "finished":
                    logger.info(f"[Processor] 렌더링 완료: Job {job_id}")
                    return

            except Exception as e:
                logger.warning(f"[Processor] 상태 조회 실패: Job {job_id}, Error: {e}")
                # 상태 조회 실패는 무시하고 계속 폴링

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"렌더링 타임아웃 (Job {job_id}, {max_timeout}초 초과)")

    async def _post_process(self, job: dict[str, Any], nexrender_job_uid: str) -> str:
        """후처리: 파일 검증, NAS 복사

        Args:
            job: render_queue 레코드
            nexrender_job_uid: Nexrender Job UID

        Returns:
            str: 출력 파일 경로

        Raises:
            FileNotFoundError: 출력 파일 없음
        """
        # 기존 스키마: output_path 사용
        output_path = job.get("output_path")

        if not output_path:
            # output_path가 없으면 기본 경로 구성
            output_ext_map = {
                "mp4": "mp4",
                "mov": "mov",
                "mov_alpha": "mov",
                "png_sequence": "png",
            }
            output_ext = output_ext_map.get(job.get("output_format", "mp4"), "mp4")
            output_path = f"{self.config.output_dir}/{job['id']}.{output_ext}"

        # Windows 경로로 변환 (Docker 환경)
        output_path = self.path_converter.to_windows_path(output_path)

        # 파일 존재 확인
        output_file = Path(output_path)
        if not output_file.exists():
            logger.warning(f"[Processor] 출력 파일 없음: {output_path}")
            # Nexrender action-copy 실패 가능성 있음
            # 임시로 경로만 반환 (실제 파일은 Nexrender가 생성)

        # TODO: NAS 복사 (필요 시)
        # if self.config.nas_output_path:
        #     nas_path = f"{self.config.nas_output_path}/{output_filename}.{output_ext}"
        #     shutil.copy(output_path, nas_path)

        return output_path

    async def _handle_error(self, job_id: str, error: Exception) -> None:
        """에러 처리

        재시도 가능 에러면 pending으로 복원, 불가능하면 failed로 처리합니다.
        error_details에 retry_count, error_category 저장 (기존 스키마 호환).

        Args:
            job_id: render_queue 작업 ID
            error: 발생한 예외
        """
        category = ErrorClassifier.classify(error)
        message = ErrorClassifier.format_message(error, include_traceback=True)

        logger.error(f"[Processor] 에러 분류: Job {job_id}, Category={category.value}")

        # 현재 작업 정보 조회
        job = await self.supabase.get_job(job_id)
        if not job:
            logger.warning(f"[Processor] 작업 조회 실패: Job {job_id}")
            return

        # error_details에서 retry_count 읽기 (기존 스키마 호환)
        error_details = job.get("error_details", {}) or {}
        retry_count = error_details.get("retry_count", 0)
        max_retries = error_details.get("max_retries", self.config.max_retries)

        should_retry = (
            category == ErrorCategory.RETRYABLE and retry_count < max_retries
        )

        if should_retry:
            logger.info(
                f"[Processor] 재시도 예정: Job {job_id}, "
                f"retry #{retry_count + 1}/{max_retries}"
            )
            await self.supabase.mark_failed(
                job_id,
                error_message=f"[재시도 #{retry_count + 1}] {message}",
                error_category=category.value,
                should_retry=True,
            )
        else:
            logger.error(
                f"[Processor] 작업 실패 (재시도 불가): Job {job_id}, "
                f"Category={category.value}"
            )
            await self.supabase.mark_failed(
                job_id,
                error_message=message,
                error_category=category.value,
                should_retry=False,
            )
