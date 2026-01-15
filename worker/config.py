"""
워커 설정

환경변수 기반 설정 관리.
"""

import os
from dataclasses import dataclass, field

from lib.path_utils import PathMapping


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
            path_mappings=path_mappings if path_mappings else cls.__dataclass_fields__["path_mappings"].default_factory(),
        )
