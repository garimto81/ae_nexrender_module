"""
Pytest 설정 및 공통 Fixture
"""

import os
from typing import Any

import pytest

from worker.config import WorkerConfig
from lib.path_utils import PathConverter, PathMapping


@pytest.fixture
def sample_gfx_data() -> dict[str, Any]:
    """샘플 GFX 데이터 (기본)"""
    from tests.sample_data import generate_sample_gfx_data
    return generate_sample_gfx_data("basic")


@pytest.fixture
def sample_gfx_data_multi_slot() -> dict[str, Any]:
    """샘플 GFX 데이터 (여러 슬롯)"""
    from tests.sample_data import generate_sample_gfx_data
    return generate_sample_gfx_data("multi_slot")


@pytest.fixture
def sample_gfx_data_with_images() -> dict[str, Any]:
    """샘플 GFX 데이터 (이미지 포함)"""
    from tests.sample_data import generate_sample_gfx_data
    return generate_sample_gfx_data("with_images")


@pytest.fixture
def sample_template() -> dict[str, Any]:
    """샘플 템플릿 데이터 (레거시)"""
    from tests.sample_data import generate_sample_template
    return generate_sample_template()


@pytest.fixture
def sample_layer_data() -> dict[str, Any]:
    """샘플 레이어 데이터 (레거시)"""
    from tests.sample_data import generate_sample_layer_data
    return generate_sample_layer_data()


@pytest.fixture
def worker_config() -> WorkerConfig:
    """테스트용 WorkerConfig

    환경변수 대신 하드코딩된 값 사용.
    """
    return WorkerConfig(
        supabase_url="https://test.supabase.co",
        supabase_service_key="test_key",
        nexrender_url="http://localhost:3000",
        nexrender_secret="",
        aep_template_dir="C:/claude/automation_ae/templates",
        output_dir="C:/claude/automation_ae/output",
        nas_output_path="//NAS/renders",
        render_timeout=1800,
        max_retries=3,
        health_port=8080,
        path_mappings=[
            PathMapping("/app/templates", "C:/claude/automation_ae/templates"),
            PathMapping("/app/output", "C:/claude/automation_ae/output"),
            PathMapping("/nas/renders", "//NAS/renders"),
        ],
    )


@pytest.fixture
def path_converter(worker_config: WorkerConfig) -> PathConverter:
    """테스트용 PathConverter

    WorkerConfig의 경로 매핑 사용.
    """
    return PathConverter(mappings=worker_config.path_mappings)


@pytest.fixture
def test_aep_path(worker_config: WorkerConfig) -> str:
    """테스트용 AEP 파일 경로"""
    return f"{worker_config.aep_template_dir}/CyprusDesign/CyprusDesign.aep"


@pytest.fixture
def test_composition_name() -> str:
    """테스트용 컴포지션 이름"""
    return "1-Hand-for-hand play is currently in progress"


# 환경변수 기반 설정 (실제 환경 테스트용)
@pytest.fixture
def worker_config_from_env() -> WorkerConfig:
    """환경변수에서 로드한 WorkerConfig

    실제 .env 파일이 있을 때만 사용.
    """
    return WorkerConfig.from_env()
