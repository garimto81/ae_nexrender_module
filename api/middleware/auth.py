"""
API Key 인증 미들웨어

X-API-Key 헤더를 검증하여 인증을 수행합니다.
"""

import os

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader


class APIKeyAuth:
    """API Key 인증 클래스

    환경변수 또는 설정에서 유효한 API Key 목록을 로드하여 검증합니다.

    사용법:
        ```python
        auth = APIKeyAuth()

        @app.get("/protected")
        async def protected_endpoint(api_key: str = Depends(auth)):
            return {"message": "Authenticated"}
        ```
    """

    # 헤더 이름
    HEADER_NAME = "X-API-Key"

    def __init__(
        self,
        api_keys: list[str] | None = None,
        auto_error: bool = True,
    ):
        """
        Args:
            api_keys: 유효한 API Key 목록 (None이면 환경변수에서 로드)
            auto_error: 인증 실패 시 자동 에러 발생 여부
        """
        self._api_keys = api_keys or self._load_api_keys_from_env()
        self._auto_error = auto_error
        self._header_scheme = APIKeyHeader(
            name=self.HEADER_NAME,
            auto_error=auto_error,
        )

    def _load_api_keys_from_env(self) -> list[str]:
        """환경변수에서 API Key 로드

        환경변수:
            - API_KEYS: 쉼표로 구분된 API Key 목록
            - API_KEY: 단일 API Key
            - API_KEY_PRODUCTION: 프로덕션 API Key
            - API_KEY_STAGING: 스테이징 API Key
            - API_KEY_DEV: 개발 API Key (기본값 포함)

        Returns:
            유효한 API Key 목록
        """
        keys: list[str] = []

        # 쉼표 구분 목록
        if api_keys_str := os.getenv("API_KEYS"):
            keys.extend(k.strip() for k in api_keys_str.split(",") if k.strip())

        # 개별 환경변수
        for env_var in [
            "API_KEY",
            "API_KEY_PRODUCTION",
            "API_KEY_STAGING",
            "API_KEY_DEV",
            "RENDER_API_KEY",
        ]:
            if key := os.getenv(env_var):
                keys.append(key)

        # 개발 환경 기본 키 (프로덕션에서는 반드시 변경 필요)
        if not keys and os.getenv("ENV", "dev") == "dev":
            keys.append("dev-api-key-change-in-production")

        return list(set(keys))  # 중복 제거

    async def __call__(self, request: Request) -> str | None:
        """API Key 검증

        Args:
            request: FastAPI Request 객체

        Returns:
            검증된 API Key 또는 None

        Raises:
            HTTPException: 인증 실패 시 (auto_error=True인 경우)
        """
        # 헤더에서 API Key 추출
        api_key = request.headers.get(self.HEADER_NAME)

        # 키가 없는 경우
        if not api_key:
            if self._auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "MISSING_API_KEY",
                        "message": f"Missing {self.HEADER_NAME} header",
                    },
                )
            return None

        # 키 검증
        if api_key not in self._api_keys:
            if self._auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "INVALID_API_KEY",
                        "message": "Invalid API key",
                    },
                )
            return None

        return api_key

    def add_key(self, key: str) -> None:
        """API Key 추가 (런타임)

        Args:
            key: 추가할 API Key
        """
        if key and key not in self._api_keys:
            self._api_keys.append(key)

    def remove_key(self, key: str) -> None:
        """API Key 제거 (런타임)

        Args:
            key: 제거할 API Key
        """
        if key in self._api_keys:
            self._api_keys.remove(key)

    def reload_keys(self) -> None:
        """환경변수에서 API Key 다시 로드"""
        self._api_keys = self._load_api_keys_from_env()

    @property
    def key_count(self) -> int:
        """등록된 API Key 수"""
        return len(self._api_keys)


# 싱글톤 인스턴스
_auth_instance: APIKeyAuth | None = None


def get_api_key_auth() -> APIKeyAuth:
    """API Key 인증 인스턴스 반환 (싱글톤)"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = APIKeyAuth()
    return _auth_instance
