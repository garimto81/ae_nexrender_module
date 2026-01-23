"""
API 요청 스키마 정의

외부 시스템에서 렌더링을 요청할 때 사용하는 Pydantic 모델입니다.
기존 Supabase 스키마(aep_project, aep_comp_name)와 호환됩니다.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """출력 포맷"""

    MP4 = "mp4"
    MOV = "mov"
    MOV_ALPHA = "mov_alpha"  # 알파 채널 포함
    PNG_SEQUENCE = "png_sequence"


class RenderPriority(int, Enum):
    """렌더링 우선순위 (낮을수록 높은 우선순위)"""

    URGENT = 1
    HIGH = 10
    NORMAL = 100
    LOW = 500
    BACKGROUND = 1000


class RenderRequest(BaseModel):
    """렌더링 요청 스키마

    외부 시스템에서 렌더링을 요청할 때 사용하는 메인 스키마입니다.
    기존 Supabase 스키마(aep_project, aep_comp_name)와 호환됩니다.

    Example:
        ```python
        request = RenderRequest(
            aep_project="/app/templates/CyprusDesign/CyprusDesign.aep",
            aep_comp_name="1-Hand-for-hand play is currently in progress",
            gfx_data={
                "single_fields": {
                    "event_name": "WSOP SUPER CIRCUIT CYPRUS",
                    "tournament_name": "EVENT #12"
                }
            }
        )
        ```
    """

    # 필수 필드
    aep_project: str = Field(
        ...,
        description="AEP 프로젝트 파일 경로 (Docker/Windows 경로 모두 허용)",
        examples=["/app/templates/CyprusDesign/CyprusDesign.aep"],
    )
    aep_comp_name: str = Field(
        ...,
        description="After Effects 컴포지션 이름",
        examples=["1-Hand-for-hand play is currently in progress"],
    )
    gfx_data: dict[str, Any] = Field(
        ...,
        description="GFX 렌더링 데이터 (slots, single_fields 포함)",
        examples=[
            {
                "slots": [{"slot_index": 1, "fields": {"name": "PHIL IVEY"}}],
                "single_fields": {"event_name": "WSOP Cyprus"},
            }
        ],
    )

    # 선택 필드 (기본값 있음)
    output_format: OutputFormat = Field(
        default=OutputFormat.MP4,
        description="출력 포맷",
    )
    output_path: str | None = Field(
        default=None,
        description="출력 파일 전체 경로 (None이면 자동 생성)",
    )
    priority: RenderPriority | int = Field(
        default=RenderPriority.NORMAL,
        description="렌더링 우선순위 (낮을수록 높은 우선순위)",
    )

    # 고급 옵션
    callback_url: str | None = Field(
        default=None,
        description="렌더링 완료 시 Webhook 호출 URL",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="외부 시스템 추적용 메타데이터 (cue_item_id 등)",
    )

    # 캐시 옵션
    use_cache: bool = Field(
        default=True,
        description="동일 데이터 캐시 사용 여부",
    )

    # 렌더 타입 (기존 스키마 호환)
    render_type: str = Field(
        default="custom",
        description="렌더 타입 (chip_count, leaderboard, player_info, custom 등)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "aep_project": "/app/templates/CyprusDesign/CyprusDesign.aep",
                "aep_comp_name": "1-Hand-for-hand play is currently in progress",
                "gfx_data": {
                    "single_fields": {
                        "event_name": "WSOP SUPER CIRCUIT CYPRUS",
                        "tournament_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY",
                    }
                },
                "output_format": "mp4",
                "priority": 100,
            }
        }
    }


class RenderBatchRequest(BaseModel):
    """배치 렌더링 요청 (여러 작업 한번에 제출)

    Example:
        ```python
        batch = RenderBatchRequest(
            jobs=[
                RenderRequest(...),
                RenderRequest(...),
            ]
        )
        ```
    """

    jobs: list[RenderRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="렌더링 작업 목록 (최대 100개)",
    )

    # 배치 레벨 설정
    batch_priority: RenderPriority | int = Field(
        default=RenderPriority.NORMAL,
        description="배치 전체 기본 우선순위 (개별 작업에서 오버라이드 가능)",
    )
    batch_callback_url: str | None = Field(
        default=None,
        description="모든 작업 완료 시 Webhook 호출 URL",
    )
    batch_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="배치 레벨 메타데이터",
    )


# =============================================================================
# 매핑 검증 요청 스키마 (Phase 1: DB 매핑값과 컴포지션 선택 API 호출 관계)
# =============================================================================


class MappingValidationRequest(BaseModel):
    """매핑 검증 요청 스키마

    POST /api/v1/mapping/validate 요청에 사용됩니다.

    Example:
        ```python
        request = MappingValidationRequest(
            template_name="CyprusDesign",
            composition_name="_Feature Table Leaderboard",
            gfx_data={
                "slots": [
                    {"slot_index": 1, "fields": {"name": "PHIL IVEY", "chips": "250,000"}}
                ],
                "single_fields": {"event_name": "WSOP"}
            }
        )
        ```
    """

    template_name: str = Field(
        ...,
        description="AEP 템플릿 이름",
        examples=["CyprusDesign"],
    )
    composition_name: str = Field(
        ...,
        description="컴포지션 이름",
        examples=["_Feature Table Leaderboard"],
    )
    gfx_data: dict[str, Any] = Field(
        ...,
        description="검증할 GFX 데이터 (slots, single_fields 포함)",
        examples=[
            {
                "slots": [
                    {"slot_index": 1, "fields": {"name": "PHIL IVEY", "chips": "250,000"}}
                ],
                "single_fields": {"event_name": "WSOP Cyprus"},
            }
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_name": "CyprusDesign",
                "composition_name": "_Feature Table Leaderboard",
                "gfx_data": {
                    "slots": [
                        {
                            "slot_index": 1,
                            "fields": {"name": "PHIL IVEY", "chips": "250,000"},
                        }
                    ],
                    "single_fields": {"event_name": "WSOP SUPER CIRCUIT CYPRUS"},
                },
            }
        }
    }
