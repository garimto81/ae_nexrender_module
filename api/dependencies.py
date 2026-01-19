"""
FastAPI 의존성 주입 모듈

ConfigStore, SupabaseClient, Auth 등의 의존성을 관리합니다.
"""

import os
from typing import Any

from fastapi import Depends, Request

from .middleware.auth import APIKeyAuth, get_api_key_auth


# ============================================================================
# API Key 인증 의존성
# ============================================================================
async def verify_api_key(
    request: Request,
    auth: APIKeyAuth = Depends(get_api_key_auth),
) -> str:
    """API Key 검증 의존성

    Args:
        request: FastAPI Request 객체
        auth: APIKeyAuth 인스턴스

    Returns:
        검증된 API Key
    """
    return await auth(request)


# ============================================================================
# ConfigStore 의존성
# ============================================================================
_config_store: Any = None


def set_config_store(store: Any) -> None:
    """ConfigStore 설정 (앱 시작 시 호출)

    Args:
        store: ConfigStore 인스턴스
    """
    global _config_store
    _config_store = store


def get_config_store() -> Any:
    """ConfigStore 의존성

    Returns:
        ConfigStore 인스턴스 또는 None
    """
    return _config_store


# ============================================================================
# Supabase 클라이언트 의존성
# ============================================================================
_supabase_client: Any = None


def set_supabase_client(client: Any) -> None:
    """Supabase 클라이언트 설정 (앱 시작 시 호출)

    Args:
        client: SupabaseQueueClient 인스턴스
    """
    global _supabase_client
    _supabase_client = client


def get_supabase_client() -> Any:
    """Supabase 클라이언트 의존성

    Returns:
        SupabaseQueueClient 인스턴스 또는 None
    """
    return _supabase_client


# ============================================================================
# 환경 설정 의존성
# ============================================================================
class Settings:
    """앱 설정 클래스"""

    def __init__(self):
        self.env = os.getenv("ENV", "dev")
        self.debug = self.env == "dev"

        # API 서버 설정
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))

        # Supabase 설정
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")

        # Nexrender 설정
        self.nexrender_url = os.getenv("NEXRENDER_URL", "http://localhost:3000")
        self.nexrender_secret = os.getenv("NEXRENDER_SECRET", "")

        # 설정 파일 경로
        self.config_path = os.getenv("CONFIG_PATH", "config/api_config.yaml")
        self.mappings_dir = os.getenv("MAPPINGS_DIR", "config/mappings")


_settings: Settings | None = None


def get_settings() -> Settings:
    """앱 설정 의존성 (싱글톤)

    Returns:
        Settings 인스턴스
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# ============================================================================
# Request Context 의존성
# ============================================================================
async def get_request_id(request: Request) -> str:
    """요청 ID 추출 (추적용)

    Args:
        request: FastAPI Request

    Returns:
        요청 ID (헤더에서 추출하거나 생성)
    """
    import uuid

    # X-Request-ID 헤더 우선
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())[:8]

    return request_id
