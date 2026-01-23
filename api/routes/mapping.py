"""
매핑 API 라우터

GFX 필드와 AEP 레이어 간의 매핑 정보 조회 및 검증 API를 제공합니다.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from lib.mapping_loader import MappingLoader
from lib.mapping_validator import MappingValidator

from ..dependencies import verify_api_key
from ..schemas.request import MappingValidationRequest
from ..schemas.response import (
    CompositionMappingResponse,
    ErrorResponse,
    MappingSummaryItem,
    MappingSummaryResponse,
    MappingValidationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/mapping",
    tags=["Mapping"],
    dependencies=[Depends(verify_api_key)],
)

# 모듈 레벨 싱글톤 (서버 시작 시 초기화)
_mapping_loader: MappingLoader | None = None
_validator: MappingValidator | None = None


def get_mapping_loader() -> MappingLoader:
    """MappingLoader 의존성"""
    global _mapping_loader
    if _mapping_loader is None:
        _mapping_loader = MappingLoader()
    return _mapping_loader


def get_validator() -> MappingValidator:
    """MappingValidator 의존성"""
    global _validator
    if _validator is None:
        _validator = MappingValidator(get_mapping_loader())
    return _validator


@router.get(
    "",
    response_model=MappingSummaryResponse,
    summary="전체 매핑 상태 요약",
    description="모든 템플릿과 컴포지션의 매핑 상태를 요약합니다.",
)
async def get_all_mappings(
    mapping_loader: MappingLoader = Depends(get_mapping_loader),
) -> MappingSummaryResponse:
    """전체 매핑 상태 요약

    Returns:
        MappingSummaryResponse: 템플릿별 매핑 요약
    """
    templates_summary: list[MappingSummaryItem] = []
    total_compositions = 0

    # 매핑 디렉토리 스캔
    mappings_dir = mapping_loader.mappings_dir

    if mappings_dir.exists():
        for mapping_file in mappings_dir.glob("*.yaml"):
            template_name = mapping_file.stem
            mapping = mapping_loader.load(template_name)

            compositions = list(mapping.get("compositions", {}).keys())
            composition_count = len(compositions)

            templates_summary.append(
                MappingSummaryItem(
                    template=template_name,
                    composition_count=composition_count,
                    compositions=compositions,
                )
            )

            total_compositions += composition_count

        # JSON 파일도 확인 (YAML 없는 경우)
        for mapping_file in mappings_dir.glob("*.json"):
            template_name = mapping_file.stem
            # 이미 YAML로 로드된 경우 건너뜀
            if any(t.template == template_name for t in templates_summary):
                continue

            mapping = mapping_loader.load(template_name)
            compositions = list(mapping.get("compositions", {}).keys())
            composition_count = len(compositions)

            templates_summary.append(
                MappingSummaryItem(
                    template=template_name,
                    composition_count=composition_count,
                    compositions=compositions,
                )
            )

            total_compositions += composition_count

    return MappingSummaryResponse(
        total_templates=len(templates_summary),
        total_compositions=total_compositions,
        templates=templates_summary,
    )


@router.get(
    "/{template_name}/{composition_name:path}",
    response_model=CompositionMappingResponse,
    summary="컴포지션 매핑 상세 조회",
    description="특정 템플릿의 컴포지션 매핑 정보를 상세 조회합니다.",
    responses={
        404: {"model": ErrorResponse, "description": "템플릿 또는 컴포지션을 찾을 수 없음"},
    },
)
async def get_composition_mapping(
    template_name: str,
    composition_name: str,
    mapping_loader: MappingLoader = Depends(get_mapping_loader),
    validator: MappingValidator = Depends(get_validator),
) -> CompositionMappingResponse:
    """컴포지션 매핑 상세 조회

    Args:
        template_name: 템플릿 이름
        composition_name: 컴포지션 이름

    Returns:
        CompositionMappingResponse: 매핑 상세 정보
    """
    # 매핑 파일 로드
    mapping = mapping_loader.load(template_name)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "MAPPING_NOT_FOUND",
                "message": f"Mapping file for template '{template_name}' not found",
            },
        )

    # 컴포지션 존재 확인
    compositions = mapping.get("compositions", {})
    if composition_name not in compositions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "COMPOSITION_NOT_FOUND",
                "message": f"Composition '{composition_name}' not found in template '{template_name}'",
                "available_compositions": list(compositions.keys()),
            },
        )

    # 컴포지션 정보 조회
    comp_info = compositions[composition_name]
    field_mappings = comp_info.get("field_mappings", {})

    # 슬롯 수 및 단일 필드 수 계산
    slot_count = validator.get_slot_count(template_name, composition_name)
    single_field_count = validator.get_single_field_count(template_name, composition_name)

    # 버전 및 업데이트 시간
    version = mapping.get("version", "1.0")
    last_updated_str = mapping.get("template", {}).get("last_updated")
    last_updated = None
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    return CompositionMappingResponse(
        template=template_name,
        composition=composition_name,
        description=comp_info.get("description"),
        field_mappings=field_mappings,
        slot_count=slot_count,
        single_field_count=single_field_count,
        version=version,
        last_updated=last_updated,
    )


@router.post(
    "/validate",
    response_model=MappingValidationResult,
    summary="GFX 데이터 매핑 검증",
    description="GFX 데이터가 매핑 파일과 일치하는지 검증합니다.",
    responses={
        200: {"description": "검증 결과 (유효/무효 모두 200 반환)"},
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
    },
)
async def validate_mapping(
    request: MappingValidationRequest,
    validator: MappingValidator = Depends(get_validator),
) -> MappingValidationResult:
    """GFX 데이터 매핑 검증

    Args:
        request: 검증 요청 (template_name, composition_name, gfx_data)

    Returns:
        MappingValidationResult: 검증 결과
    """
    result = validator.validate(
        template_name=request.template_name,
        composition_name=request.composition_name,
        gfx_data=request.gfx_data,
    )

    return MappingValidationResult(
        is_valid=result.is_valid,
        matched_fields=result.matched_fields,
        missing_fields=result.missing_fields,
        fallback_fields=result.fallback_fields,
        warnings=result.warnings,
        errors=result.errors,
    )


