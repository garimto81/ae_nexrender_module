"""
공용 타입 정의

Nexrender 작업 관련 Enum, Dataclass, Pydantic 모델.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """출력 포맷"""

    MP4 = "mp4"
    MOV = "mov"
    MOV_ALPHA = "mov_alpha"
    PNG_SEQUENCE = "png_sequence"


class RenderStatus(str, Enum):
    """렌더링 작업 상태 (orch_render_status ENUM과 매핑)"""

    PENDING = "pending"
    QUEUED = "queued"  # 기존 스키마 호환
    PREPARING = "preparing"
    RENDERING = "rendering"
    ENCODING = "encoding"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderType(str, Enum):
    """렌더링 타입 (orch_render_type ENUM과 매핑)"""

    CHIP_COUNT = "chip_count"
    LEADERBOARD = "leaderboard"
    PLAYER_INFO = "player_info"
    HAND_REPLAY = "hand_replay"
    ELIMINATION = "elimination"
    PAYOUT = "payout"
    CUSTOM = "custom"


class ErrorCategory(str, Enum):
    """에러 카테고리"""

    RETRYABLE = "retryable"  # 네트워크 오류, 일시적 장애
    NON_RETRYABLE = "non_retryable"  # 설정 오류, 파일 없음
    UNKNOWN = "unknown"


@dataclass
class JobConfig:
    """Job 빌드 설정"""

    aep_project_path: str
    composition_name: str
    output_format: str = "mp4"
    output_dir: str = ""
    output_filename: str = ""
    callback_url: str | None = None


class RenderJob(BaseModel):
    """Supabase render_queue 테이블 매핑 모델

    기존 Supabase 스키마(orch_render_status, orch_render_type)와 호환.
    """

    # 기본 식별자
    id: str
    job_id: str | None = None  # job_queue FK
    cue_item_id: str | None = None

    # 렌더 타입 및 설정
    render_type: RenderType = RenderType.CUSTOM
    aep_project: str  # 기존: aep_project_path → aep_project
    aep_comp_name: str  # 기존: composition_name → aep_comp_name
    gfx_data: dict[str, Any]
    data_hash: str | None = None

    # 출력 설정
    output_format: str = "mp4"
    output_path: str | None = None  # 기존: output_dir + output_filename 통합
    output_resolution: str = "1920x1080"
    output_frame_rate: int = 30
    output_codec: str = "h264"
    output_quality: str = "high"

    # 프레임 설정
    start_frame: int = 0
    end_frame: int | None = None
    duration_seconds: float | None = None

    # 상태 관리
    status: RenderStatus = RenderStatus.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    current_frame: int = 0
    total_frames: int | None = None

    # 우선순위 및 시간
    priority: int = Field(default=100, ge=1)
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    estimated_completion: str | None = None

    # 출력 결과
    output_file_size: int | None = None
    output_duration_seconds: float | None = None
    render_duration_ms: int | None = None

    # 에러 처리
    error_message: str | None = None
    error_details: dict[str, Any] | None = (
        None  # 기존: error_category, retry_count 통합
    )
    error_frame: int | None = None

    # 워커 정보
    worker_id: str | None = None  # TEXT 타입 (UUID 아님)
    worker_host: str | None = None
    aerender_pid: int | None = None

    # 캐시
    cache_hit: bool = False
    cached_output_path: str | None = None

    # 메타데이터 (nexrender_job_id 등 저장)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 호환성 프로퍼티
    @property
    def composition_name(self) -> str:
        """composition_name 별칭 (하위 호환)"""
        return self.aep_comp_name

    @property
    def aep_project_path(self) -> str:
        """aep_project_path 별칭 (하위 호환)"""
        return self.aep_project

    @property
    def nexrender_job_id(self) -> str | None:
        """metadata에서 nexrender_job_id 조회"""
        return self.metadata.get("nexrender_job_id")

    @property
    def retry_count(self) -> int:
        """error_details에서 retry_count 조회"""
        if self.error_details:
            return self.error_details.get("retry_count", 0)
        return 0

    @property
    def max_retries(self) -> int:
        """error_details에서 max_retries 조회"""
        if self.error_details:
            return self.error_details.get("max_retries", 3)
        return 3
