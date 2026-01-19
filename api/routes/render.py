"""
렌더링 API 라우터

렌더링 작업 제출, 상태 조회, 취소 등의 핵심 API를 제공합니다.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_config_store, get_supabase_client, verify_api_key
from ..schemas.request import RenderBatchRequest, RenderRequest
from ..schemas.response import (
    ErrorResponse,
    RenderBatchResponse,
    RenderDetailResponse,
    RenderListResponse,
    RenderResponse,
    RenderStatus,
    RenderStatusResponse,
)

router = APIRouter(
    prefix="/api/v1/render",
    tags=["Render"],
    dependencies=[Depends(verify_api_key)],
)


@router.post(
    "",
    response_model=RenderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="렌더링 작업 제출",
    description="새로운 렌더링 작업을 큐에 추가합니다.",
    responses={
        201: {"description": "작업이 성공적으로 큐에 추가됨"},
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
        401: {"model": ErrorResponse, "description": "인증 실패"},
        422: {"model": ErrorResponse, "description": "유효성 검사 실패"},
    },
)
async def submit_render(
    request: RenderRequest,
    supabase_client: Any = Depends(get_supabase_client),
    config_store: Any = Depends(get_config_store),
) -> RenderResponse:
    """렌더링 작업 제출

    Args:
        request: 렌더링 요청 데이터

    Returns:
        RenderResponse: 생성된 작업 정보
    """
    # 작업 ID 생성
    job_id = str(uuid.uuid4())
    queued_at = datetime.now(timezone.utc)

    # 컴포지션 유효성 검사 (옵션)
    if config_store:
        # TODO: 컴포지션 존재 여부 확인
        pass

    # DB에 작업 추가
    if supabase_client:
        try:
            job_data = {
                "id": job_id,
                "aep_project": request.aep_project,
                "aep_comp_name": request.aep_comp_name,
                "gfx_data": request.gfx_data,
                "output_format": request.output_format.value,
                "output_path": request.output_path,
                "priority": (
                    request.priority.value
                    if hasattr(request.priority, "value")
                    else request.priority
                ),
                "status": "pending",
                "render_type": request.render_type,
                "metadata": request.metadata,
                "queued_at": queued_at.isoformat(),
            }

            await supabase_client.insert_job(job_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "DB_ERROR", "message": str(e)},
            )

    # 대기열 위치 계산 (옵션)
    position = None
    if supabase_client:
        try:
            position = await supabase_client.get_pending_count()
        except Exception:
            pass

    return RenderResponse(
        id=job_id,
        status=RenderStatus.PENDING,
        queued_at=queued_at,
        position_in_queue=position,
    )


@router.post(
    "/batch",
    response_model=RenderBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="배치 렌더링 제출",
    description="여러 렌더링 작업을 한번에 큐에 추가합니다.",
)
async def submit_batch_render(
    request: RenderBatchRequest,
    supabase_client: Any = Depends(get_supabase_client),
    config_store: Any = Depends(get_config_store),
) -> RenderBatchResponse:
    """배치 렌더링 작업 제출

    Args:
        request: 배치 렌더링 요청

    Returns:
        RenderBatchResponse: 배치 처리 결과
    """
    batch_id = f"batch-{uuid.uuid4()}"
    jobs: list[RenderResponse] = []
    errors: list[dict[str, Any]] = []

    for idx, job_request in enumerate(request.jobs):
        try:
            # 개별 작업 제출
            response = await submit_render(
                request=job_request,
                supabase_client=supabase_client,
                config_store=config_store,
            )
            jobs.append(response)
        except HTTPException as e:
            errors.append(
                {
                    "index": idx,
                    "error": e.detail.get("error", "UNKNOWN"),
                    "message": e.detail.get("message", str(e)),
                }
            )
        except Exception as e:
            errors.append(
                {
                    "index": idx,
                    "error": "UNKNOWN_ERROR",
                    "message": str(e),
                }
            )

    return RenderBatchResponse(
        batch_id=batch_id,
        total=len(request.jobs),
        accepted=len(jobs),
        rejected=len(errors),
        jobs=jobs,
        errors=errors,
    )


@router.get(
    "",
    response_model=RenderListResponse,
    summary="작업 목록 조회",
    description="렌더링 작업 목록을 조회합니다. 필터링 및 페이지네이션을 지원합니다.",
)
async def list_renders(
    status_filter: RenderStatus | None = Query(
        None, alias="status", description="상태 필터"
    ),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    supabase_client: Any = Depends(get_supabase_client),
) -> RenderListResponse:
    """작업 목록 조회

    Args:
        status_filter: 상태 필터
        page: 페이지 번호
        page_size: 페이지 크기

    Returns:
        RenderListResponse: 작업 목록
    """
    items: list[RenderStatusResponse] = []
    total = 0

    if supabase_client:
        try:
            # 필터 조건 구성
            filters = {}
            if status_filter:
                filters["status"] = status_filter.value

            # DB 조회
            result = await supabase_client.list_jobs(
                filters=filters,
                offset=(page - 1) * page_size,
                limit=page_size,
            )

            total = result.get("total", 0)

            for job in result.get("items", []):
                items.append(
                    RenderStatusResponse(
                        id=job["id"],
                        status=RenderStatus(job.get("status", "pending")),
                        progress=job.get("progress", 0),
                        queued_at=job.get("queued_at"),
                        started_at=job.get("started_at"),
                        completed_at=job.get("completed_at"),
                        error_message=job.get("error_message"),
                        worker_id=job.get("worker_id"),
                        metadata=job.get("metadata", {}),
                    )
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "DB_ERROR", "message": str(e)},
            )

    return RenderListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.get(
    "/{job_id}",
    response_model=RenderDetailResponse,
    summary="작업 상세 조회",
    description="특정 렌더링 작업의 상세 정보를 조회합니다.",
    responses={
        200: {"description": "작업 정보"},
        404: {"model": ErrorResponse, "description": "작업을 찾을 수 없음"},
    },
)
async def get_render(
    job_id: str,
    supabase_client: Any = Depends(get_supabase_client),
) -> RenderDetailResponse:
    """작업 상세 조회

    Args:
        job_id: 작업 ID

    Returns:
        RenderDetailResponse: 작업 상세 정보
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "DB_UNAVAILABLE", "message": "Database not configured"},
        )

    try:
        job = await supabase_client.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Job {job_id} not found"},
            )

        return RenderDetailResponse(
            id=job["id"],
            status=RenderStatus(job.get("status", "pending")),
            progress=job.get("progress", 0),
            queued_at=job.get("queued_at"),
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            current_frame=job.get("current_frame"),
            total_frames=job.get("total_frames"),
            render_duration_ms=job.get("render_duration_ms"),
            output_path=job.get("output_path"),
            output_file_size=job.get("output_file_size"),
            output_duration_seconds=job.get("output_duration_seconds"),
            error_message=job.get("error_message"),
            error_category=job.get("error_details", {}).get("error_category"),
            retry_count=job.get("error_details", {}).get("retry_count", 0),
            worker_id=job.get("worker_id"),
            metadata=job.get("metadata", {}),
            # 상세 필드
            aep_project=job.get("aep_project", ""),
            aep_comp_name=job.get("aep_comp_name", ""),
            gfx_data=job.get("gfx_data", {}),
            output_format=job.get("output_format", "mp4"),
            priority=job.get("priority", 100),
            render_type=job.get("render_type", "custom"),
            cache_hit=job.get("cache_hit", False),
            cached_output_path=job.get("cached_output_path"),
            callback_url=job.get("metadata", {}).get("callback_url"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DB_ERROR", "message": str(e)},
        )


@router.get(
    "/{job_id}/status",
    response_model=RenderStatusResponse,
    summary="작업 상태 조회 (경량)",
    description="특정 렌더링 작업의 상태만 조회합니다. 폴링용 경량 API입니다.",
)
async def get_render_status(
    job_id: str,
    supabase_client: Any = Depends(get_supabase_client),
) -> RenderStatusResponse:
    """작업 상태 조회 (경량)

    Args:
        job_id: 작업 ID

    Returns:
        RenderStatusResponse: 작업 상태 정보
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "DB_UNAVAILABLE", "message": "Database not configured"},
        )

    try:
        job = await supabase_client.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Job {job_id} not found"},
            )

        return RenderStatusResponse(
            id=job["id"],
            status=RenderStatus(job.get("status", "pending")),
            progress=job.get("progress", 0),
            queued_at=job.get("queued_at"),
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            current_frame=job.get("current_frame"),
            total_frames=job.get("total_frames"),
            render_duration_ms=job.get("render_duration_ms"),
            output_path=job.get("output_path"),
            error_message=job.get("error_message"),
            worker_id=job.get("worker_id"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DB_ERROR", "message": str(e)},
        )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="작업 취소",
    description="대기 중인 렌더링 작업을 취소합니다. 이미 진행 중인 작업은 취소되지 않을 수 있습니다.",
    responses={
        204: {"description": "작업 취소됨"},
        404: {"model": ErrorResponse, "description": "작업을 찾을 수 없음"},
        409: {"model": ErrorResponse, "description": "이미 완료되었거나 취소된 작업"},
    },
)
async def cancel_render(
    job_id: str,
    supabase_client: Any = Depends(get_supabase_client),
) -> None:
    """작업 취소

    Args:
        job_id: 작업 ID
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "DB_UNAVAILABLE", "message": "Database not configured"},
        )

    try:
        job = await supabase_client.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Job {job_id} not found"},
            )

        current_status = job.get("status", "")

        # 이미 완료/취소된 작업은 취소 불가
        if current_status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "INVALID_STATE",
                    "message": f"Cannot cancel job in '{current_status}' state",
                },
            )

        # 상태 업데이트
        await supabase_client.update_job_status(job_id, "cancelled")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DB_ERROR", "message": str(e)},
        )
