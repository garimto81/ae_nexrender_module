"""
ConfigStore 및 핫 리로드 테스트
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestConfigStore:
    """ConfigStore 테스트"""

    @pytest.fixture
    def temp_config_dir(self):
        """임시 설정 디렉토리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 설정 파일 생성
            config_path = Path(tmpdir) / "api_config.yaml"
            config_data = {
                "version": "1.0.0",
                "templates": {
                    "TestTemplate": {
                        "path": "/app/templates/Test.aep",
                        "mapping_file": str(Path(tmpdir) / "TestTemplate.yaml"),
                        "compositions": ["Main", "Secondary"],
                        "default_composition": "Main",
                    }
                },
                "db_schema": {
                    "table": "render_queue",
                    "field_mappings": {
                        "aep_project": "aep_project",
                        "status": "status",
                    },
                },
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # 매핑 파일 생성
            mapping_path = Path(tmpdir) / "TestTemplate.yaml"
            mapping_data = {
                "compositions": {
                    "Main": {
                        "field_mappings": {
                            "event_name": "EVENT_LAYER",
                            "title": "TITLE_LAYER",
                        }
                    }
                }
            }
            with open(mapping_path, "w") as f:
                yaml.dump(mapping_data, f)

            yield tmpdir, str(config_path)

    @pytest.mark.asyncio
    async def test_reload_config(self, temp_config_dir):
        """설정 리로드 테스트"""
        tmpdir, config_path = temp_config_dir

        # ConfigStore 싱글톤 리셋
        from config.config_manager import ConfigStore

        ConfigStore._instance = None

        store = ConfigStore()
        await store.reload(config_path)

        assert store.version == "1.0.0"
        assert "TestTemplate" in store._templates

    @pytest.mark.asyncio
    async def test_get_template(self, temp_config_dir):
        """템플릿 조회 테스트"""
        tmpdir, config_path = temp_config_dir

        from config.config_manager import ConfigStore

        ConfigStore._instance = None

        store = ConfigStore()
        await store.reload(config_path)

        template = store.get_template("TestTemplate")
        assert template is not None
        assert template.name == "TestTemplate"
        assert template.path == "/app/templates/Test.aep"
        assert "Main" in template.compositions

    @pytest.mark.asyncio
    async def test_get_layer_mapping(self, temp_config_dir):
        """레이어 매핑 조회 테스트"""
        tmpdir, config_path = temp_config_dir

        from config.config_manager import ConfigStore

        ConfigStore._instance = None

        store = ConfigStore()
        await store.reload(config_path)

        # 매핑 조회
        layer_name = store.get_layer_mapping("TestTemplate", "Main", "event_name")
        assert layer_name == "EVENT_LAYER"

        # 없는 필드
        layer_name = store.get_layer_mapping("TestTemplate", "Main", "nonexistent")
        assert layer_name is None

    @pytest.mark.asyncio
    async def test_map_api_to_db(self, temp_config_dir):
        """API → DB 필드 매핑 테스트"""
        tmpdir, config_path = temp_config_dir

        from config.config_manager import ConfigStore

        ConfigStore._instance = None

        store = ConfigStore()
        await store.reload(config_path)

        api_data = {
            "aep_project": "/app/test.aep",
            "status": "pending",
            "custom_field": "value",  # 매핑 없음
        }

        db_data = store.map_api_to_db(api_data)

        assert db_data["aep_project"] == "/app/test.aep"
        assert db_data["status"] == "pending"
        assert db_data["custom_field"] == "value"  # 매핑 없으면 그대로

    @pytest.mark.asyncio
    async def test_env_var_substitution(self):
        """환경변수 치환 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_data = {
                "version": "1.0.0",
                "templates": {
                    "Test": {
                        "path": "${TEMPLATE_PATH}",
                        "api_key": "$API_KEY",
                    }
                },
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # 환경변수 설정
            with patch.dict(
                os.environ,
                {
                    "TEMPLATE_PATH": "/custom/path.aep",
                    "API_KEY": "secret123",
                },
            ):
                from config.config_manager import ConfigStore

                ConfigStore._instance = None

                store = ConfigStore()
                await store.reload(str(config_path))

                template = store.get_template("Test")
                assert template.path == "/custom/path.aep"

    @pytest.mark.asyncio
    async def test_reload_callback(self, temp_config_dir):
        """리로드 콜백 테스트"""
        tmpdir, config_path = temp_config_dir

        from config.config_manager import ConfigStore

        ConfigStore._instance = None

        store = ConfigStore()

        callback_called = []

        async def on_reload():
            callback_called.append(True)

        store.on_reload(on_reload)
        await store.reload(config_path)

        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_missing_config_creates_default(self):
        """설정 파일 없을 때 기본 생성 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent" / "config.yaml"

            from config.config_manager import ConfigStore

            ConfigStore._instance = None

            store = ConfigStore()
            await store.reload(str(config_path))

            # 기본 설정으로 생성됨
            assert store.version == "1.0.0"
            assert config_path.exists()


class TestConfigWatcher:
    """ConfigWatcher 핫 리로드 테스트"""

    @pytest.mark.asyncio
    async def test_watcher_detects_change(self):
        """파일 변경 감지 테스트 (watchdog 설치 시)"""
        pytest.importorskip("watchdog")

        # 이 테스트는 실제 파일 시스템 이벤트가 필요하므로
        # 통합 테스트에서 수행하는 것이 좋음
        pass
