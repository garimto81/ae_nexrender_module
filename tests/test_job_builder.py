"""
JobBuilder 단위 테스트

GFX 데이터와 템플릿 기반 Job JSON 생성 테스트.
"""

from typing import Any

from lib.job_builder import JobConfig, NexrenderJobBuilder


class TestJobConfig:
    """JobConfig 테스트"""

    def test_create_minimal_config(self):
        """최소 설정으로 생성"""
        config = JobConfig(
            aep_project_path="C:/test/test.aep",
            composition_name="Main",
        )
        assert config.aep_project_path == "C:/test/test.aep"
        assert config.composition_name == "Main"
        assert config.output_format == "mp4"  # 기본값

    def test_create_full_config(self):
        """전체 설정으로 생성"""
        config = JobConfig(
            aep_project_path="C:/test/test.aep",
            composition_name="Main",
            output_format="mov",
            output_dir="C:/output",
            output_filename="result.mov",
            callback_url="http://localhost:8000/callback",
        )
        assert config.output_format == "mov"
        assert config.output_dir == "C:/output"
        assert config.callback_url == "http://localhost:8000/callback"


class TestBuildFromGFXData:
    """GFX 데이터 기반 Job 빌드 테스트"""

    def test_build_basic_gfx_data(self, sample_gfx_data: dict[str, Any]):
        """기본 GFX 데이터에서 Job JSON 생성"""
        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_dir="C:/output",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_gfx_data(sample_gfx_data, "test-job-001")

        # 기본 구조 검증
        assert "template" in result
        assert "assets" in result
        assert "actions" in result

        # Template 섹션 검증
        assert result["template"]["src"] == "file:///C:/templates/test.aep"
        assert result["template"]["composition"] == "Main"
        assert result["template"]["outputExt"] == "mp4"

        # Assets 검증
        assets = result["assets"]
        assert len(assets) >= 4  # slot1_name, slot1_chips, table_id, tournament

        # 슬롯 필드 검증
        slot_assets = [a for a in assets if a["layerName"].startswith("slot1_")]
        assert len(slot_assets) == 2
        assert any(a["value"] == "PHIL IVEY" for a in slot_assets)
        assert any(a["value"] == "1,234,567" for a in slot_assets)

        # 단일 필드 검증
        single_assets = [a for a in assets if not a["layerName"].startswith("slot")]
        assert len(single_assets) == 2
        assert any(a["value"] == "Table 1" for a in single_assets)
        assert any(a["value"] == "WSOP 2024" for a in single_assets)

        # Actions 검증
        assert "postrender" in result["actions"]
        copy_action = result["actions"]["postrender"][0]
        assert copy_action["module"] == "@nexrender/action-copy"
        assert "C:/output/test-job-001.mp4" in copy_action["output"]

    def test_build_multi_slot_gfx_data(
        self, sample_gfx_data_multi_slot: dict[str, Any]
    ):
        """여러 슬롯 GFX 데이터에서 Job JSON 생성"""
        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_dir="C:/output",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_gfx_data(sample_gfx_data_multi_slot, "multi-slot")

        assets = result["assets"]

        # 8개 슬롯 * 2개 필드 = 16개 슬롯 에셋
        slot_assets = [a for a in assets if a["layerName"].startswith("slot")]
        assert len(slot_assets) == 16

        # 슬롯별로 검증
        for i in range(1, 9):
            slot_name_asset = next(
                a for a in assets if a["layerName"] == f"slot{i}_name"
            )
            assert slot_name_asset["value"] == f"Player {i}"

    def test_build_with_images(self, sample_gfx_data_with_images: dict[str, Any]):
        """이미지 에셋 포함 GFX 데이터에서 Job JSON 생성"""
        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_dir="C:/output",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_gfx_data(sample_gfx_data_with_images, "with-images")

        assets = result["assets"]

        # 이미지 에셋 확인
        image_assets = [a for a in assets if a.get("type") == "image"]
        assert len(image_assets) == 1
        assert image_assets[0]["layerName"] == "background_image"
        assert "file:///" in image_assets[0]["src"]

    def test_build_with_callback_url(self, sample_gfx_data: dict[str, Any]):
        """콜백 URL 포함 Job JSON 생성"""
        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_dir="C:/output",
            callback_url="http://localhost:8000/callback",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_gfx_data(sample_gfx_data, "callback-test")

        assert "callback" in result
        assert result["callback"] == "http://localhost:8000/callback/callback-test"

    def test_output_format_mov(self, sample_gfx_data: dict[str, Any]):
        """출력 포맷 MOV 설정"""
        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_dir="C:/output",
            output_format="mov",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_gfx_data(sample_gfx_data, "mov-test")

        assert result["template"]["outputExt"] == "mov"
        assert "mov-test.mov" in result["actions"]["postrender"][0]["output"]


class TestBuildFromTemplate:
    """템플릿 기반 Job 빌드 테스트 (레거시)"""

    def test_build_from_template_basic(
        self,
        sample_template: dict[str, Any],
        sample_layer_data: dict[str, Any],
    ):
        """템플릿 기반 Job JSON 생성 (텍스트 레이어)"""
        config = JobConfig(
            aep_project_path="/app/templates/test.aep",
            composition_name="Main",
            output_dir="/app/output",
        )
        builder = NexrenderJobBuilder(config)

        result = builder.build_from_template(sample_template, sample_layer_data, 123)

        # Assets 검증
        assets = result["assets"]

        # 텍스트 레이어
        text_assets = [a for a in assets if a["type"] == "data"]
        assert len(text_assets) == 2
        assert any(
            a["layerName"] == "player1_name" and a["value"] == "PHIL IVEY"
            for a in text_assets
        )

        # 이미지 레이어
        image_assets = [a for a in assets if a["type"] == "image"]
        assert len(image_assets) == 2
        assert any(a["layerName"] == "background_image" for a in image_assets)
        assert any(a["layerName"] == "logo" for a in image_assets)


class TestPrivateMethods:
    """내부 메서드 테스트"""

    def test_get_output_extension_mp4(self):
        """출력 확장자 결정 (mp4)"""
        config = JobConfig(
            aep_project_path="C:/test.aep",
            composition_name="Main",
            output_format="mp4",
        )
        builder = NexrenderJobBuilder(config)

        assert builder._get_output_extension() == "mp4"

    def test_get_output_extension_mov(self):
        """출력 확장자 결정 (mov)"""
        config = JobConfig(
            aep_project_path="C:/test.aep",
            composition_name="Main",
            output_format="mov",
        )
        builder = NexrenderJobBuilder(config)

        assert builder._get_output_extension() == "mov"

    def test_get_output_extension_png_sequence(self):
        """출력 확장자 결정 (PNG 시퀀스)"""
        config = JobConfig(
            aep_project_path="C:/test.aep",
            composition_name="Main",
            output_format="png_sequence",
        )
        builder = NexrenderJobBuilder(config)

        assert builder._get_output_extension() == "png"
