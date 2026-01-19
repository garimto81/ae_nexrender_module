"""
FastAPI 앱 정의 및 라우터 통합

AE-Nexrender 렌더링 API 서버의 메인 모듈입니다.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .dependencies import get_settings, set_config_store, set_supabase_client
from .routes import config_router, health_router, render_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """앱 라이프사이클 관리

    시작 시:
        - ConfigStore 초기화
        - Supabase 클라이언트 초기화
        - 설정 파일 로드

    종료 시:
        - 리소스 정리
    """
    settings = get_settings()

    # ConfigStore 초기화
    try:
        from config.config_manager import ConfigStore

        config_store = ConfigStore()
        await config_store.reload(settings.config_path)
        set_config_store(config_store)
        logger.info(f"[Server] ConfigStore 초기화 완료: v{config_store._version}")
    except ImportError:
        logger.warning("[Server] ConfigStore 모듈 없음 - 설정 기능 비활성화")
    except Exception as e:
        logger.warning(f"[Server] ConfigStore 초기화 실패: {e}")

    # Supabase 클라이언트 초기화
    if settings.supabase_url and settings.supabase_key:
        try:
            from worker.supabase_client import SupabaseQueueClient

            supabase_client = SupabaseQueueClient(
                url=settings.supabase_url,
                key=settings.supabase_key,
            )
            set_supabase_client(supabase_client)
            logger.info("[Server] Supabase 클라이언트 초기화 완료")
        except ImportError:
            logger.warning("[Server] Supabase 클라이언트 모듈 없음 - DB 기능 비활성화")
        except Exception as e:
            logger.warning(f"[Server] Supabase 클라이언트 초기화 실패: {e}")
    else:
        logger.warning("[Server] Supabase 설정 없음 - DB 기능 비활성화")

    yield

    # 리소스 정리
    logger.info("[Server] 서버 종료")


def create_app(
    title: str = "AE-Nexrender Render API",
    version: str = "1.0.0",
    debug: bool = False,
) -> FastAPI:
    """FastAPI 앱 생성

    Args:
        title: API 제목
        version: API 버전
        debug: 디버그 모드

    Returns:
        FastAPI 앱 인스턴스
    """
    settings = get_settings()

    app = FastAPI(
        title=title,
        version=version,
        description="""
# AE-Nexrender 렌더링 API

After Effects 렌더링 작업을 HTTP API로 제출하고 관리합니다.

## 주요 기능

- **렌더링 작업 제출**: POST /api/v1/render
- **배치 렌더링**: POST /api/v1/render/batch
- **상태 조회**: GET /api/v1/render/{id}/status
- **작업 취소**: DELETE /api/v1/render/{id}
- **설정 핫 리로드**: POST /api/v1/config/reload

## 인증

모든 API 요청에는 `X-API-Key` 헤더가 필요합니다.
        """,
        debug=debug or settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(health_router)  # /health
    app.include_router(render_router)  # /api/v1/render
    app.include_router(config_router)  # /api/v1/config

    # 글로벌 예외 핸들러
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """글로벌 예외 핸들러"""
        logger.exception(f"[Server] 처리되지 않은 예외: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(exc) if settings.debug else None,
            },
        )

    return app


# 기본 앱 인스턴스
app = create_app()


# 직접 실행 시
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
