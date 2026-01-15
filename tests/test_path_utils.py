"""
경로 변환 유틸리티 테스트

Docker ↔ Windows 경로 변환, file:// URL 변환 테스트.
"""

import pytest

from lib.path_utils import PathConverter, PathMapping


class TestPathConverter:
    """PathConverter 기본 기능 테스트"""

    def test_to_windows_path_template(self, path_converter: PathConverter):
        """Docker 경로 → Windows 경로 (템플릿)"""
        docker_path = "/app/templates/CyprusDesign/CyprusDesign.aep"
        result = path_converter.to_windows_path(docker_path)

        assert result == "C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep"

    def test_to_windows_path_output(self, path_converter: PathConverter):
        """Docker 경로 → Windows 경로 (출력)"""
        docker_path = "/app/output/render_001.mp4"
        result = path_converter.to_windows_path(docker_path)

        assert result == "C:/claude/automation_ae/output/render_001.mp4"

    def test_to_windows_path_nas(self, path_converter: PathConverter):
        """Docker 경로 → Windows 경로 (NAS UNC)"""
        docker_path = "/nas/renders/final/output.mp4"
        result = path_converter.to_windows_path(docker_path)

        assert result == "//NAS/renders/final/output.mp4"

    def test_to_windows_path_no_match(self, path_converter: PathConverter):
        """매핑되지 않는 경로는 그대로 반환"""
        docker_path = "/unknown/path/file.mp4"
        result = path_converter.to_windows_path(docker_path)

        assert result == "/unknown/path/file.mp4"

    def test_to_docker_path_template(self, path_converter: PathConverter):
        """Windows 경로 → Docker 경로 (템플릿)"""
        windows_path = "C:/claude/automation_ae/templates/file.aep"
        result = path_converter.to_docker_path(windows_path)

        assert result == "/app/templates/file.aep"

    def test_to_docker_path_output(self, path_converter: PathConverter):
        """Windows 경로 → Docker 경로 (출력)"""
        windows_path = "C:/claude/automation_ae/output/result.mp4"
        result = path_converter.to_docker_path(windows_path)

        assert result == "/app/output/result.mp4"

    def test_to_docker_path_backslash(self, path_converter: PathConverter):
        """백슬래시 경로도 정상 변환"""
        windows_path = r"C:\claude\automation_ae\templates\file.aep"
        result = path_converter.to_docker_path(windows_path)

        assert result == "/app/templates/file.aep"

    def test_to_docker_path_no_match(self, path_converter: PathConverter):
        """매핑되지 않는 경로는 그대로 반환"""
        windows_path = "D:/unknown/file.mp4"
        result = path_converter.to_docker_path(windows_path)

        assert result == "D:/unknown/file.mp4"


class TestFileURL:
    """file:// URL 변환 테스트"""

    def test_to_file_url_docker_path(self, path_converter: PathConverter):
        """Docker 경로를 file:// URL로 변환"""
        docker_path = "/app/templates/file.aep"
        result = path_converter.to_file_url(docker_path)

        assert result == "file:///C:/claude/automation_ae/templates/file.aep"

    def test_to_file_url_windows_path(self, path_converter: PathConverter):
        """Windows 경로를 file:// URL로 변환"""
        windows_path = "C:/templates/file.aep"
        result = path_converter.to_file_url(windows_path)

        assert result == "file:///C:/templates/file.aep"

    def test_to_file_url_unc_path(self, path_converter: PathConverter):
        """UNC 경로 (NAS)를 file:// URL로 변환"""
        unc_path = "//NAS/renders/output.mp4"
        result = path_converter.to_file_url(unc_path)

        assert result == "file://NAS/renders/output.mp4"

    def test_to_file_url_already_url(self, path_converter: PathConverter):
        """이미 file:// URL인 경우 그대로 반환"""
        file_url = "file:///C:/templates/file.aep"
        result = path_converter.to_file_url(file_url)

        assert result == "file:///C:/templates/file.aep"

    def test_to_file_url_backslash(self, path_converter: PathConverter):
        """백슬래시 경로도 슬래시로 변환"""
        windows_path = r"C:\templates\file.aep"
        result = path_converter.to_file_url(windows_path)

        assert result == "file:///C:/templates/file.aep"


class TestCustomMappings:
    """커스텀 경로 매핑 테스트"""

    def test_custom_mappings(self):
        """사용자 정의 경로 매핑"""
        custom_mappings = [
            PathMapping("/mnt/data", "D:/Data"),
            PathMapping("/mnt/projects", "E:/Projects"),
        ]
        converter = PathConverter(mappings=custom_mappings)

        # Docker → Windows
        assert converter.to_windows_path("/mnt/data/file.txt") == "D:/Data/file.txt"
        assert converter.to_windows_path("/mnt/projects/src/main.py") == "E:/Projects/src/main.py"

        # Windows → Docker
        assert converter.to_docker_path("D:/Data/file.txt") == "/mnt/data/file.txt"
        assert converter.to_docker_path("E:/Projects/src/main.py") == "/mnt/projects/src/main.py"

    def test_empty_mappings(self):
        """빈 매핑 리스트 (DEFAULT_MAPPINGS 사용)"""
        # mappings=None이면 DEFAULT_MAPPINGS 사용
        converter = PathConverter(mappings=None)

        docker_path = "/app/templates/file.aep"
        result = converter.to_windows_path(docker_path)
        assert result == "C:/claude/automation_ae/templates/file.aep"


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_path_with_spaces(self, path_converter: PathConverter):
        """공백 포함 경로"""
        docker_path = "/app/templates/My Project/file.aep"
        result = path_converter.to_windows_path(docker_path)

        assert result == "C:/claude/automation_ae/templates/My Project/file.aep"

    def test_path_with_special_chars(self, path_converter: PathConverter):
        """특수 문자 포함 경로"""
        docker_path = "/app/templates/project_v2.0/file-final.aep"
        result = path_converter.to_windows_path(docker_path)

        assert "project_v2.0/file-final.aep" in result

    def test_nested_deep_path(self, path_converter: PathConverter):
        """깊은 중첩 경로"""
        docker_path = "/app/templates/a/b/c/d/e/file.aep"
        result = path_converter.to_windows_path(docker_path)

        assert result == "C:/claude/automation_ae/templates/a/b/c/d/e/file.aep"

    def test_trailing_slash(self, path_converter: PathConverter):
        """경로 끝 슬래시"""
        docker_path = "/app/templates/"
        result = path_converter.to_windows_path(docker_path)

        assert result == "C:/claude/automation_ae/templates/"
