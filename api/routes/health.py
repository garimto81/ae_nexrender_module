"""
헬스체크 API 라우터

서버 상태, 컴포넌트 연결 상태, 대기 작업 수 등을 반환합니다.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import get_config_store, get_supabase_client
from ..schemas.response import HealthResponse

router = APIRouter(tags=["Health"])

# 서버 시작 시각
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="헬스체크",
    description="서버 상태 및 컴포넌트 연결 상태를 반환합니다.",
)
async def health_check(
    config_store: Any = Depends(get_config_store),
    supabase_client: Any = Depends(get_supabase_client),
) -> HealthResponse:
    """서버 헬스체크

    Returns:
        HealthResponse: 서버 상태 정보
    """
    # 가동 시간 계산
    uptime = int(time.time() - _start_time)

    # DB 연결 상태 확인
    db_status = "unknown"
    pending_jobs = 0
    try:
        if supabase_client:
            pending_jobs = await supabase_client.get_pending_count()
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Nexrender 상태 확인 (TODO: 실제 연결 확인 구현)
    nexrender_status = "unknown"

    # 설정 버전
    version = "1.0.0"
    if config_store:
        version = getattr(config_store, "_version", "1.0.0")

    return HealthResponse(
        status="ok",
        version=version,
        worker_count=0,  # TODO: 활성 워커 수 조회
        pending_jobs=pending_jobs,
        uptime_seconds=uptime,
        database=db_status,
        nexrender=nexrender_status,
    )


@router.get(
    "/health/live",
    summary="Liveness 체크",
    description="서버가 살아있는지 확인합니다. (Kubernetes liveness probe용)",
)
async def liveness() -> dict[str, str]:
    """Liveness 체크 (경량)"""
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness 체크",
    description="서버가 요청을 처리할 준비가 되었는지 확인합니다. (Kubernetes readiness probe용)",
)
async def readiness(
    supabase_client: Any = Depends(get_supabase_client),
) -> dict[str, str]:
    """Readiness 체크

    DB 연결이 정상이면 ready 반환
    """
    try:
        if supabase_client:
            await supabase_client.get_pending_count()
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
