"""
API 응답 스키마 정의

렌더링 작업의 상태, 진행률, 결과를 반환하는 Pydantic 모델입니다.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RenderStatus(str, Enum):
    """렌더링 작업 상태"""

    PENDING = "pending"  # 대기 중 (큐에 추가됨)
    QUEUED = "queued"  # Nexrender 큐에 제출됨
    PREPARING = "preparing"  # 워커가 작업 준비 중
    RENDERING = "rendering"  # 렌더링 진행 중
    ENCODING = "encoding"  # 인코딩 중
    UPLOADING = "uploading"  # 업로드 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패
    CANCELLED = "cancelled"  # 취소됨


class RenderResponse(BaseModel):
    """렌더링 응답 스키마 (작업 제출 결과)

    POST /api/v1/render 응답으로 반환됩니다.
    """

    id: str = Field(..., description="렌더링 작업 ID (UUID)")
    status: RenderStatus = Field(..., description="현재 상태")
    queued_at: datetime = Field(..., description="큐 등록 시각")
    estimated_completion: datetime | None = Field(
        default=None,
        description="예상 완료 시각",
    )
    position_in_queue: int | None = Field(
        default=None,
        description="대기열 내 위치",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "queued_at": "2026-01-16T10:30:00Z",
                "estimated_completion": "2026-01-16T10:35:00Z",
                "position_in_queue": 3,
            }
        }
    }


class RenderStatusResponse(BaseModel):
    """렌더링 상태 조회 응답

    GET /api/v1/render/{id}/status 응답으로 반환됩니다.
    경량 조회용으로 최소한의 정보만 포함합니다.
    """

    id: str = Field(..., description="렌더링 작업 ID")
    status: RenderStatus = Field(..., description="현재 상태")
    progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="진행률 (0-100)",
    )

    # 시간 정보
    queued_at: datetime | None = Field(default=None, description="큐 등록 시각")
    started_at: datetime | None = Field(default=None, description="렌더링 시작 시각")
    completed_at: datetime | None = Field(default=None, description="완료 시각")
    estimated_completion: datetime | None = Field(
        default=None,
        description="예상 완료 시각",
    )

    # 현재 진행 상태
    current_frame: int | None = Field(default=None, description="현재 프레임")
    total_frames: int | None = Field(default=None, description="총 프레임 수")
    render_duration_ms: int | None = Field(
        default=None,
        description="렌더링 소요 시간 (밀리초)",
    )

    # 출력 정보 (완료 시)
    output_path: str | None = Field(default=None, description="출력 파일 경로")
    output_file_size: int | None = Field(
        default=None, description="출력 파일 크기 (바이트)"
    )
    output_duration_seconds: float | None = Field(
        default=None,
        description="출력 영상 길이 (초)",
    )

    # 에러 정보 (실패 시)
    error_message: str | None = Field(default=None, description="에러 메시지")
    error_category: str | None = Field(
        default=None,
        description="에러 카테고리 (retryable, non_retryable, unknown)",
    )
    retry_count: int = Field(default=0, description="재시도 횟수")

    # 워커 정보
    worker_id: str | None = Field(default=None, description="처리 중인 워커 ID")

    # 메타데이터
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="메타데이터 (nexrender_job_id 등)",
    )


class RenderDetailResponse(RenderStatusResponse):
    """렌더링 상세 정보 응답

    GET /api/v1/render/{id} 응답으로 반환됩니다.
    RenderStatusResponse를 확장하여 모든 필드를 포함합니다.
    """

    # 원본 요청 정보
    aep_project: str = Field(..., description="AEP 프로젝트 파일 경로")
    aep_comp_name: str = Field(..., description="컴포지션 이름")
    gfx_data: dict[str, Any] = Field(
        default_factory=dict, description="GFX 렌더링 데이터"
    )
    output_format: str = Field(default="mp4", description="출력 포맷")
    priority: int = Field(default=100, description="우선순위")
    render_type: str = Field(default="custom", description="렌더 타입")

    # 캐시 정보
    cache_hit: bool = Field(default=False, description="캐시 히트 여부")
    cached_output_path: str | None = Field(
        default=None,
        description="캐시된 출력 파일 경로",
    )

    # 콜백 정보
    callback_url: str | None = Field(default=None, description="Webhook URL")


class RenderBatchResponse(BaseModel):
    """배치 렌더링 응답

    POST /api/v1/render/batch 응답으로 반환됩니다.
    """

    batch_id: str = Field(..., description="배치 ID")
    total: int = Field(..., description="총 작업 수")
    accepted: int = Field(..., description="수락된 작업 수")
    rejected: int = Field(..., description="거부된 작업 수")
    jobs: list[RenderResponse] = Field(..., description="개별 작업 응답")
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="거부된 작업의 에러 정보",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "batch_id": "batch-550e8400-e29b-41d4-a716-446655440000",
                "total": 5,
                "accepted": 4,
                "rejected": 1,
                "jobs": [
                    {
                        "id": "job-1",
                        "status": "pending",
                        "queued_at": "2026-01-16T10:30:00Z",
                    }
                ],
                "errors": [
                    {
                        "index": 2,
                        "error": "VALIDATION_ERROR",
                        "message": "Invalid composition name",
                    }
                ],
            }
        }
    }


class RenderListResponse(BaseModel):
    """렌더링 작업 목록 응답

    GET /api/v1/render 응답으로 반환됩니다.
    페이지네이션을 지원합니다.
    """

    items: list[RenderStatusResponse] = Field(..., description="작업 목록")
    total: int = Field(..., description="전체 작업 수")
    page: int = Field(default=1, description="현재 페이지")
    page_size: int = Field(default=20, description="페이지 크기")
    has_next: bool = Field(default=False, description="다음 페이지 존재 여부")
    has_prev: bool = Field(default=False, description="이전 페이지 존재 여부")


class ErrorResponse(BaseModel):
    """API 에러 응답"""

    error: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: dict[str, Any] | None = Field(
        default=None,
        description="상세 에러 정보",
    )
    request_id: str | None = Field(default=None, description="요청 ID (추적용)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "VALIDATION_ERROR",
                "message": "Invalid composition name",
                "details": {"field": "aep_comp_name", "value": "NonExistentComp"},
                "request_id": "req-550e8400",
            }
        }
    }


class HealthResponse(BaseModel):
    """헬스체크 응답

    GET /health 응답으로 반환됩니다.
    """

    status: str = Field(default="ok", description="서버 상태")
    version: str = Field(..., description="API 버전")
    worker_count: int = Field(default=0, description="활성 워커 수")
    pending_jobs: int = Field(default=0, description="대기 중인 작업 수")
    uptime_seconds: int = Field(default=0, description="서버 가동 시간 (초)")

    # 컴포넌트 상태
    database: str = Field(default="unknown", description="DB 연결 상태")
    nexrender: str = Field(default="unknown", description="Nexrender 서버 상태")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "worker_count": 2,
                "pending_jobs": 5,
                "uptime_seconds": 3600,
                "database": "connected",
                "nexrender": "connected",
            }
        }
    }


class ConfigResponse(BaseModel):
    """설정 조회 응답

    GET /api/v1/config/* 응답으로 반환됩니다.
    """

    version: str = Field(..., description="설정 버전")
    last_updated: datetime | None = Field(
        default=None, description="마지막 업데이트 시각"
    )


class TemplatesResponse(ConfigResponse):
    """템플릿 목록 응답"""

    templates: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="템플릿 정보 (이름 -> 설정)",
    )


class CompositionsResponse(ConfigResponse):
    """컴포지션 목록 응답"""

    template: str = Field(..., description="템플릿 이름")
    compositions: list[str] = Field(..., description="사용 가능한 컴포지션 목록")
