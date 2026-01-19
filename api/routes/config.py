"""
설정 API 라우터

템플릿, 컴포지션 목록 조회 및 설정 핫 리로드를 제공합니다.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_config_store, verify_api_key
from ..schemas.response import CompositionsResponse, ConfigResponse, TemplatesResponse

router = APIRouter(
    prefix="/api/v1/config",
    tags=["Config"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/templates",
    response_model=TemplatesResponse,
    summary="템플릿 목록 조회",
    description="사용 가능한 AEP 템플릿 목록을 조회합니다.",
)
async def get_templates(
    config_store: Any = Depends(get_config_store),
) -> TemplatesResponse:
    """템플릿 목록 조회

    Returns:
        TemplatesResponse: 템플릿 정보
    """
    version = "1.0.0"
    templates: dict[str, dict[str, Any]] = {}

    if config_store:
        version = getattr(config_store, "_version", "1.0.0")

        # 템플릿 정보 수집
        for name, template in getattr(config_store, "_templates", {}).items():
            templates[name] = {
                "path": getattr(template, "path", ""),
                "compositions": getattr(template, "compositions", []),
                "default_composition": getattr(template, "default_composition", ""),
                "metadata": getattr(template, "metadata", {}),
            }

    return TemplatesResponse(
        version=version,
        last_updated=datetime.now(timezone.utc),
        templates=templates,
    )


@router.get(
    "/templates/{template_name}/compositions",
    response_model=CompositionsResponse,
    summary="컴포지션 목록 조회",
    description="특정 템플릿의 사용 가능한 컴포지션 목록을 조회합니다.",
)
async def get_compositions(
    template_name: str,
    config_store: Any = Depends(get_config_store),
) -> CompositionsResponse:
    """컴포지션 목록 조회

    Args:
        template_name: 템플릿 이름

    Returns:
        CompositionsResponse: 컴포지션 목록
    """
    version = "1.0.0"
    compositions: list[str] = []

    if config_store:
        version = getattr(config_store, "_version", "1.0.0")

        template = getattr(config_store, "_templates", {}).get(template_name)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Template '{template_name}' not found",
                },
            )

        compositions = getattr(template, "compositions", [])

    return CompositionsResponse(
        version=version,
        last_updated=datetime.now(timezone.utc),
        template=template_name,
        compositions=compositions,
    )


@router.post(
    "/reload",
    response_model=ConfigResponse,
    summary="설정 핫 리로드",
    description="설정 파일을 다시 로드합니다. 매핑 파일 변경 시 사용합니다.",
)
async def reload_config(
    config_store: Any = Depends(get_config_store),
) -> ConfigResponse:
    """설정 핫 리로드

    Returns:
        ConfigResponse: 리로드 후 설정 버전
    """
    if not config_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "CONFIG_UNAVAILABLE",
                "message": "Config store not initialized",
            },
        )

    try:
        await config_store.reload()
        version = getattr(config_store, "_version", "1.0.0")

        return ConfigResponse(
            version=version,
            last_updated=datetime.now(timezone.utc),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "RELOAD_FAILED",
                "message": str(e),
            },
        )
