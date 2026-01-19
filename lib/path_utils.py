"""
Docker ↔ Windows 경로 변환 유틸리티

문제:
- Docker 컨테이너 내부 경로: /app/templates/file.aep
- Windows 호스트 경로: C:/claude/automation_ae/templates/file.aep
- Nexrender는 Windows 경로 필요 (file:///C:/...)

해결:
- 설정 파일 기반 경로 매핑
- 양방향 변환 지원
"""

from typing import NamedTuple


class PathMapping(NamedTuple):
    """경로 매핑 규칙"""

    docker_path: str
    windows_path: str


class PathConverter:
    """Docker ↔ Windows 경로 변환기"""

    DEFAULT_MAPPINGS = [
        PathMapping("/app/templates", "C:/claude/automation_ae/templates"),
        PathMapping("/app/output", "C:/claude/automation_ae/output"),
        PathMapping("/nas/renders", "//NAS/renders"),
    ]

    def __init__(self, mappings: list[PathMapping] | None = None):
        """
        Args:
            mappings: 경로 매핑 규칙 리스트. None이면 DEFAULT_MAPPINGS 사용.
        """
        self.mappings = mappings or self.DEFAULT_MAPPINGS

    def to_windows_path(self, docker_path: str) -> str:
        """Docker 경로 → Windows 경로

        Args:
            docker_path: Docker 컨테이너 내부 경로 (예: /app/templates/file.aep)

        Returns:
            Windows 경로 (예: C:/claude/automation_ae/templates/file.aep)

        Examples:
            >>> converter = PathConverter()
            >>> converter.to_windows_path("/app/templates/file.aep")
            'C:/claude/automation_ae/templates/file.aep'
        """
        for mapping in self.mappings:
            if docker_path.startswith(mapping.docker_path):
                return docker_path.replace(mapping.docker_path, mapping.windows_path, 1)
        return docker_path

    def to_docker_path(self, windows_path: str) -> str:
        """Windows 경로 → Docker 경로

        Args:
            windows_path: Windows 호스트 경로 (예: C:/claude/automation_ae/templates/file.aep)

        Returns:
            Docker 경로 (예: /app/templates/file.aep)

        Examples:
            >>> converter = PathConverter()
            >>> converter.to_docker_path("C:/claude/automation_ae/templates/file.aep")
            '/app/templates/file.aep'
        """
        # 백슬래시를 슬래시로 정규화
        normalized = windows_path.replace("\\", "/")

        for mapping in self.mappings:
            if normalized.startswith(mapping.windows_path):
                return normalized.replace(mapping.windows_path, mapping.docker_path, 1)
        return windows_path

    def to_file_url(self, path: str) -> str:
        """경로를 file:// URL로 변환 (Nexrender용)

        Nexrender는 Windows에서 file:// 프로토콜을 요구합니다.
        - Windows 드라이브 경로: file:///C:/path/to/file
        - UNC 경로 (NAS): file://NAS/path/to/file

        Args:
            path: Docker 또는 Windows 경로

        Returns:
            file:// URL 형식 경로

        Examples:
            >>> converter = PathConverter()
            >>> converter.to_file_url("/app/templates/file.aep")
            'file:///C:/claude/automation_ae/templates/file.aep'
            >>> converter.to_file_url("//NAS/renders/output.mp4")
            'file://NAS/renders/output.mp4'
        """
        # 이미 file:// URL인 경우 그대로 반환
        if path.startswith("file://"):
            return path

        # Docker 경로를 Windows 경로로 변환
        windows_path = self.to_windows_path(path)

        # 백슬래시를 슬래시로 변환
        windows_path = windows_path.replace("\\", "/")

        # Windows 드라이브 경로인 경우 (C:/)
        if len(windows_path) >= 2 and windows_path[1] == ":":
            return f"file:///{windows_path}"

        # UNC 경로인 경우 (//NAS/)
        if windows_path.startswith("//"):
            return f"file:{windows_path}"

        # 이미 슬래시로 시작하는 경우
        if windows_path.startswith("/"):
            return f"file://{windows_path}"

        return f"file:///{windows_path}"
