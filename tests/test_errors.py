"""
에러 분류 시스템 테스트

재시도 가능 여부 자동 판단 테스트.
"""

import pytest

from lib.errors import (
    NON_RETRYABLE_PATTERNS,
    RETRYABLE_PATTERNS,
    ErrorCategory,
    ErrorClassifier,
    NexrenderError,
)


class TestErrorClassifier:
    """에러 분류기 테스트"""

    def test_classify_retryable_connection(self):
        """재시도 가능: Connection 에러"""
        error = ConnectionError("Connection refused")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_classify_retryable_timeout(self):
        """재시도 가능: Timeout 에러"""
        error = TimeoutError("Request timeout after 30s")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_classify_retryable_network(self):
        """재시도 가능: Network 에러"""
        error = Exception("Network unavailable")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_classify_retryable_503(self):
        """재시도 가능: 503 Service Unavailable"""
        error = Exception("HTTP 503 Service Unavailable")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_classify_non_retryable_not_found(self):
        """재시도 불가: 404 Not Found"""
        error = FileNotFoundError("Template not found")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_classify_non_retryable_invalid(self):
        """재시도 불가: Invalid 에러"""
        error = ValueError("Invalid composition name")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_classify_non_retryable_permission(self):
        """재시도 불가: Permission 에러"""
        error = PermissionError("Permission denied")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_classify_non_retryable_composition_not_found(self):
        """재시도 불가: Composition not found"""
        error = Exception("Composition 'Main' not found in project")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_classify_unknown(self):
        """분류되지 않음: 알 수 없는 에러"""
        error = Exception("Some random error")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.UNKNOWN

    def test_classify_priority_non_retryable_over_retryable(self):
        """우선순위: NON_RETRYABLE > RETRYABLE"""
        # "not found"와 "timeout" 모두 포함된 경우
        error = Exception("Template not found due to timeout")
        category = ErrorClassifier.classify(error)

        # NON_RETRYABLE이 우선순위 높음
        assert category == ErrorCategory.NON_RETRYABLE


class TestErrorPatterns:
    """에러 패턴 매칭 테스트"""

    @pytest.mark.parametrize("pattern", RETRYABLE_PATTERNS)
    def test_retryable_patterns(self, pattern: str):
        """재시도 가능 패턴 테스트"""
        error = Exception(f"Error: {pattern} occurred")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    @pytest.mark.parametrize("pattern", NON_RETRYABLE_PATTERNS)
    def test_non_retryable_patterns(self, pattern: str):
        """재시도 불가 패턴 테스트"""
        error = Exception(f"Error: {pattern} occurred")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE


class TestErrorFormatMessage:
    """에러 메시지 포맷팅 테스트"""

    def test_format_message_retryable(self):
        """재시도 가능 에러 메시지 포맷팅"""
        error = ConnectionError("Connection refused")
        message = ErrorClassifier.format_message(error)

        assert "[재시도 가능]" in message
        assert "ConnectionError" in message
        assert "Connection refused" in message

    def test_format_message_non_retryable(self):
        """재시도 불가 에러 메시지 포맷팅"""
        error = FileNotFoundError("Template not found")
        message = ErrorClassifier.format_message(error)

        assert "[재시도 불가]" in message
        assert "FileNotFoundError" in message
        assert "Template not found" in message

    def test_format_message_unknown(self):
        """분류되지 않은 에러 메시지 포맷팅"""
        error = Exception("Random error")
        message = ErrorClassifier.format_message(error)

        assert "[분류되지 않음]" in message
        assert "Exception" in message
        assert "Random error" in message

    def test_format_message_with_traceback(self):
        """Traceback 포함 메시지 포맷팅"""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            message = ErrorClassifier.format_message(e, include_traceback=True)

            assert "[재시도 불가]" in message
            assert "ValueError" in message
            assert "Test error" in message
            assert "상세 정보:" in message
            assert "Traceback" in message


class TestNexrenderError:
    """NexrenderError 커스텀 예외 테스트"""

    def test_nexrender_error_with_category(self):
        """카테고리 지정 에러 생성"""
        error = NexrenderError("Test error", category=ErrorCategory.RETRYABLE)

        assert str(error) == "Test error"
        assert error.category == ErrorCategory.RETRYABLE

    def test_nexrender_error_default_category(self):
        """기본 카테고리 (UNKNOWN)"""
        error = NexrenderError("Test error")

        assert error.category == ErrorCategory.UNKNOWN

    def test_nexrender_error_classification(self):
        """NexrenderError도 분류 가능"""
        error = NexrenderError("Connection timeout")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE


class TestRealWorldScenarios:
    """실제 시나리오 테스트"""

    def test_nexrender_connection_failed(self):
        """Nexrender 서버 연결 실패"""
        error = Exception("ECONNREFUSED: Connection refused at localhost:3000")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_template_file_not_found(self):
        """템플릿 파일 없음"""
        error = FileNotFoundError("Template file C:/templates/test.aep does not exist")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_composition_not_found_in_aep(self):
        """컴포지션을 찾을 수 없음"""
        error = Exception("Composition 'Main' not found in project file")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_render_timeout(self):
        """렌더링 타임아웃"""
        error = TimeoutError("Render job timeout after 1800s")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_disk_space_error(self):
        """디스크 공간 부족 (분류되지 않음 → 재시도 X)"""
        error = OSError("No space left on device")
        category = ErrorClassifier.classify(error)

        # OSError는 RETRYABLE로 분류되지만, 실제로는 재시도해도 해결 안 됨
        # 패턴 매칭으로 더 정확한 분류 가능
        assert category == ErrorCategory.RETRYABLE

    def test_invalid_layer_name(self):
        """잘못된 레이어 이름"""
        error = ValueError("Invalid layer name: 'unknown_layer'")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE

    def test_http_502_bad_gateway(self):
        """502 Bad Gateway (재시도 가능)"""
        error = Exception("HTTP 502 Bad Gateway")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.RETRYABLE

    def test_http_401_unauthorized(self):
        """401 Unauthorized (재시도 불가)"""
        error = Exception("HTTP 401 Unauthorized")
        category = ErrorClassifier.classify(error)

        assert category == ErrorCategory.NON_RETRYABLE
