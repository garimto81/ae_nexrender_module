"""
에러 분류 시스템

재시도 가능 여부를 자동으로 판단하여 워커 재시도 로직에 활용.
"""

from enum import Enum


class ErrorCategory(str, Enum):
    """에러 카테고리"""

    RETRYABLE = "retryable"  # 네트워크 오류, 일시적 장애
    NON_RETRYABLE = "non_retryable"  # 설정 오류, 파일 없음
    UNKNOWN = "unknown"


# 재시도 가능 에러 패턴
RETRYABLE_PATTERNS = [
    "connection",
    "timeout",
    "network",
    "unavailable",
    "temporary",
    "503",
    "502",
    "504",
    "ECONNREFUSED",
    "ETIMEDOUT",
    "ENOTFOUND",
]

# 재시도 불가 에러 패턴
NON_RETRYABLE_PATTERNS = [
    "not found",
    "404",
    "invalid",
    "permission",
    "unauthorized",
    "forbidden",
    "does not exist",
    "template error",
    "composition not found",
    "missing file",
]


class NexrenderError(Exception):
    """Nexrender 기본 에러"""

    def __init__(
        self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN
    ):
        super().__init__(message)
        self.category = category


class ErrorClassifier:
    """에러 분류기"""

    @classmethod
    def classify(cls, error: Exception) -> ErrorCategory:
        """에러를 분류하여 카테고리 반환

        Args:
            error: 분류할 예외 객체

        Returns:
            ErrorCategory: 재시도 가능 여부에 따른 카테고리
        """
        error_str = str(error).lower()

        # 패턴 매칭 (우선순위: NON_RETRYABLE > RETRYABLE)
        for pattern in NON_RETRYABLE_PATTERNS:
            if pattern.lower() in error_str:
                return ErrorCategory.NON_RETRYABLE

        for pattern in RETRYABLE_PATTERNS:
            if pattern.lower() in error_str:
                return ErrorCategory.RETRYABLE

        # 예외 타입 기반 분류
        if isinstance(error, (TimeoutError, ConnectionError, OSError)):
            return ErrorCategory.RETRYABLE

        if isinstance(error, (ValueError, KeyError, FileNotFoundError)):
            return ErrorCategory.NON_RETRYABLE

        return ErrorCategory.UNKNOWN

    @classmethod
    def format_message(
        cls, error: Exception, include_traceback: bool = False
    ) -> str:
        """에러 메시지 포맷팅

        Args:
            error: 포맷팅할 예외 객체
            include_traceback: 상세 스택 트레이스 포함 여부

        Returns:
            str: 카테고리 라벨이 포함된 에러 메시지
        """
        category = cls.classify(error)
        label = {
            ErrorCategory.RETRYABLE: "[재시도 가능]",
            ErrorCategory.NON_RETRYABLE: "[재시도 불가]",
            ErrorCategory.UNKNOWN: "[분류되지 않음]",
        }

        message = f"{label[category]} {type(error).__name__}: {str(error)}"

        if include_traceback:
            import traceback

            message += f"\n\n상세 정보:\n{traceback.format_exc()}"

        return message
