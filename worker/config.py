"""
워커 설정

환경변수 기반 설정 관리.
"""

import logging
import os
from dataclasses import dataclass, field

from lib.path_utils import PathMapping

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """설정 오류 예외"""

    pass


@dataclass
class WorkerConfig:
    """워커 설정"""

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Nexrender
    nexrender_url: str = "http://localhost:3000"
    nexrender_secret: str = ""

    # 폴링 설정
    poll_interval_default: int = 10  # 기본 폴링 주기 (초)
    poll_interval_busy: int = 5  # 작업 있을 때
    poll_interval_idle: int = 30  # 작업 없을 때
    poll_interval_error: int = 60  # 에러 발생 시
    empty_poll_threshold: int = 10  # idle로 전환할 연속 빈 폴링 횟수

    # 렌더링 설정
    render_timeout: int = 1800  # 30분
    max_retries: int = 3

    # 경로 설정
    aep_template_dir: str = "D:/templates"
    output_dir: str = "D:/output"
    nas_output_path: str = "//NAS/renders"

    # 경로 매핑
    path_mappings: list[PathMapping] = field(
        default_factory=lambda: [
            PathMapping("/app/templates", "C:/claude/automation_ae/templates"),
            PathMapping("/app/output", "C:/claude/automation_ae/output"),
        ]
    )

    # 헬스 서버
    health_port: int = 8080

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """환경변수에서 설정 로드"""
        # 경로 매핑 파싱 (선택적)
        path_mappings_str = os.getenv("PATH_MAPPINGS", "")
        path_mappings = []
        if path_mappings_str:
            # 형식: "/app/templates:C:/templates,/app/output:D:/output"
            for mapping_str in path_mappings_str.split(","):
                if ":" in mapping_str:
                    docker_path, windows_path = mapping_str.split(":", 1)
                    path_mappings.append(
                        PathMapping(docker_path.strip(), windows_path.strip())
                    )

        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
            nexrender_url=os.getenv("NEXRENDER_URL", "http://localhost:3000"),
            nexrender_secret=os.getenv("NEXRENDER_SECRET", ""),
            aep_template_dir=os.getenv("AEP_TEMPLATE_DIR", "D:/templates"),
            output_dir=os.getenv("OUTPUT_DIR", "D:/output"),
            nas_output_path=os.getenv("NAS_OUTPUT_PATH", "//NAS/renders"),
            render_timeout=int(os.getenv("RENDER_TIMEOUT", "1800")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
            path_mappings=(
                path_mappings
                if path_mappings
                else cls.__dataclass_fields__["path_mappings"].default_factory()
            ),
        )

    def validate(self, strict: bool = True) -> list[str]:
        """설정값 검증

        Args:
            strict: True면 필수값 누락 시 예외 발생, False면 경고만

        Returns:
            list[str]: 검증 경고/오류 메시지 목록

        Raises:
            ConfigurationError: strict=True이고 필수값 누락 시
        """
        errors = []
        warnings = []

        # 필수 환경변수 검증
        required_fields = [
            ("supabase_url", "SUPABASE_URL"),
            ("supabase_service_key", "SUPABASE_SERVICE_KEY"),
        ]

        for field_name, env_name in required_fields:
            value = getattr(self, field_name, "")
            if not value:
                errors.append(f"필수 환경변수 누락: {env_name}")

        # URL 형식 검증
        if self.supabase_url and not self.supabase_url.startswith("http"):
            errors.append(f"잘못된 SUPABASE_URL 형식: {self.supabase_url}")

        if self.nexrender_url and not self.nexrender_url.startswith("http"):
            errors.append(f"잘못된 NEXRENDER_URL 형식: {self.nexrender_url}")

        # 경로 검증 (경고만)
        from pathlib import Path

        if self.output_dir:
            output_path = Path(self.output_dir)
            if not output_path.exists():
                warnings.append(f"출력 디렉토리 없음: {self.output_dir}")

        if self.aep_template_dir:
            template_path = Path(self.aep_template_dir)
            if not template_path.exists():
                warnings.append(f"템플릿 디렉토리 없음: {self.aep_template_dir}")

        # NAS 경로 검증 (경고만, UNC 경로는 접근 불가할 수 있음)
        if self.nas_output_path and self.nas_output_path.startswith("//"):
            nas_path = Path(self.nas_output_path)
            if not nas_path.exists():
                warnings.append(
                    f"NAS 경로 접근 불가 (나중에 확인 필요): {self.nas_output_path}"
                )

        # 숫자값 범위 검증
        if self.render_timeout < 60:
            warnings.append(f"렌더링 타임아웃이 너무 짧음: {self.render_timeout}초")
        if self.render_timeout > 7200:
            warnings.append(
                f"렌더링 타임아웃이 너무 김: {self.render_timeout}초 (2시간 초과)"
            )

        if self.max_retries < 0:
            errors.append(f"잘못된 max_retries 값: {self.max_retries}")
        if self.max_retries > 10:
            warnings.append(f"max_retries가 너무 큼: {self.max_retries}")

        # 폴링 간격 검증
        if self.poll_interval_default < 1:
            errors.append(f"폴링 간격이 너무 짧음: {self.poll_interval_default}초")

        # 경고 로깅
        for warning in warnings:
            logger.warning(f"[Config] {warning}")

        # 오류 처리
        if errors:
            for error in errors:
                logger.error(f"[Config] {error}")
            if strict:
                raise ConfigurationError(
                    f"설정 검증 실패: {len(errors)}개 오류\n" + "\n".join(errors)
                )

        return errors + warnings

    @classmethod
    def from_env_validated(cls, strict: bool = True) -> "WorkerConfig":
        """환경변수에서 설정 로드 및 검증

        Args:
            strict: True면 필수값 누락 시 예외 발생

        Returns:
            검증된 WorkerConfig 인스턴스

        Raises:
            ConfigurationError: strict=True이고 필수값 누락 시
        """
        config = cls.from_env()
        config.validate(strict=strict)
        return config
