"""
설정 관리 및 핫 리로드 시스템

AEP 템플릿, 컴포지션, DB 스키마 변경에 유연하게 대응합니다.

설계 원칙:
- 코드 변경 없이 YAML 설정만 수정하여 변경 대응
- 파일 변경 감지 기반 자동 핫 리로드
- 싱글톤 패턴으로 전역 접근

사용법:
    ```python
    store = ConfigStore()
    await store.reload()

    # 템플릿 정보 조회
    template = store.get_template("CyprusDesign")

    # 레이어 매핑 조회
    layer_name = store.get_layer_mapping(
        "CyprusDesign",
        "1-Hand-for-hand...",
        "event_name"
    )
    ```
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)


@dataclass
class TemplateConfig:
    """템플릿 설정"""

    name: str
    path: str
    mapping_file: str = ""
    compositions: list[str] = field(default_factory=list)
    default_composition: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # 런타임 로드된 매핑
    _field_mappings: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)

    def get_field_mapping(self, composition_name: str) -> dict[str, str]:
        """컴포지션별 필드 매핑 조회"""
        return self._field_mappings.get(composition_name, {})


@dataclass
class DBSchemaConfig:
    """DB 스키마 설정"""

    table: str = "render_queue"
    field_mappings: dict[str, str] = field(default_factory=dict)
    status_mappings: dict[str, str] = field(default_factory=dict)

    def map_fields(self, api_data: dict[str, Any]) -> dict[str, Any]:
        """API 필드명을 DB 컬럼명으로 변환"""
        result = {}
        for api_field, value in api_data.items():
            db_column = self.field_mappings.get(api_field, api_field)
            result[db_column] = value
        return result


class ConfigStore:
    """설정 저장소 (싱글톤)

    모든 설정은 이 클래스를 통해 접근합니다.
    핫 리로드 시 자동으로 업데이트됩니다.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._templates: dict[str, TemplateConfig] = {}
        self._db_schema: DBSchemaConfig = DBSchemaConfig()
        self._version: str = "0.0.0"
        self._lock = asyncio.Lock()
        self._callbacks: list[Callable] = []
        self._config_path: str = ""

    async def reload(self, config_path: str = "config/api_config.yaml") -> None:
        """설정 파일 리로드

        Args:
            config_path: 설정 파일 경로
        """
        async with self._lock:
            self._config_path = config_path
            logger.info(f"[ConfigStore] 설정 리로드 시작: {config_path}")

            try:
                # 설정 파일 존재 확인
                if not Path(config_path).exists():
                    logger.warning(f"[ConfigStore] 설정 파일 없음: {config_path}")
                    # 기본 설정 생성
                    self._create_default_config(config_path)

                with open(config_path, encoding="utf-8") as f:
                    raw_config = yaml.safe_load(f) or {}

                # 환경변수 치환
                config = self._substitute_env_vars(raw_config)

                # 설정 파싱
                self._version = config.get("version", "1.0.0")
                self._templates = self._parse_templates(config.get("templates", {}))
                self._db_schema = self._parse_db_schema(config.get("db_schema", {}))

                # 매핑 파일 리로드
                for template in self._templates.values():
                    await self._reload_mapping(template)

                logger.info(
                    f"[ConfigStore] 설정 리로드 완료: v{self._version}, "
                    f"{len(self._templates)}개 템플릿"
                )

                # 콜백 호출
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except Exception as e:
                        logger.error(f"[ConfigStore] 콜백 실행 실패: {e}")

            except Exception as e:
                logger.error(f"[ConfigStore] 설정 리로드 실패: {e}")
                raise

    def _create_default_config(self, config_path: str) -> None:
        """기본 설정 파일 생성"""
        default_config = {
            "version": "1.0.0",
            "templates": {
                "CyprusDesign": {
                    "path": "/app/templates/CyprusDesign/CyprusDesign.aep",
                    "mapping_file": "config/mappings/CyprusDesign.yaml",
                    "compositions": [
                        "1-Hand-for-hand play is currently in progress",
                        "1-NEXT STREAM STARTING SOON",
                    ],
                    "default_composition": "1-Hand-for-hand play is currently in progress",
                }
            },
            "db_schema": {
                "table": "render_queue",
                "field_mappings": {
                    "aep_project": "aep_project",
                    "aep_comp_name": "aep_comp_name",
                    "gfx_data": "gfx_data",
                    "output_format": "output_format",
                    "status": "status",
                    "priority": "priority",
                },
            },
        }

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"[ConfigStore] 기본 설정 파일 생성: {config_path}")

    def _substitute_env_vars(self, config: Any) -> Any:
        """설정 값에서 환경변수 치환

        ${VAR_NAME} 또는 $VAR_NAME 형식을 환경변수 값으로 치환합니다.
        """
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # ${VAR_NAME} 패턴 치환
            pattern = r"\$\{([^}]+)\}"

            def replace(match: re.Match) -> str:
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))

            result = re.sub(pattern, replace, config)

            # $VAR_NAME 패턴 치환 (단어 경계)
            pattern2 = r"\$([A-Z_][A-Z0-9_]*)"

            def replace2(match: re.Match) -> str:
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))

            return re.sub(pattern2, replace2, result)
        return config

    def _parse_templates(
        self, templates_config: dict[str, Any]
    ) -> dict[str, TemplateConfig]:
        """템플릿 설정 파싱"""
        templates = {}
        for name, config in templates_config.items():
            templates[name] = TemplateConfig(
                name=name,
                path=config.get("path", ""),
                mapping_file=config.get("mapping_file", ""),
                compositions=config.get("compositions", []),
                default_composition=config.get("default_composition", ""),
                metadata=config.get("metadata", {}),
            )
        return templates

    def _parse_db_schema(self, schema_config: dict[str, Any]) -> DBSchemaConfig:
        """DB 스키마 설정 파싱"""
        return DBSchemaConfig(
            table=schema_config.get("table", "render_queue"),
            field_mappings=schema_config.get("field_mappings", {}),
            status_mappings=schema_config.get("status_mappings", {}),
        )

    async def _reload_mapping(self, template: TemplateConfig) -> None:
        """템플릿 매핑 파일 리로드"""
        if not template.mapping_file:
            return

        mapping_path = Path(template.mapping_file)
        if not mapping_path.exists():
            logger.warning(f"[ConfigStore] 매핑 파일 없음: {mapping_path}")
            return

        try:
            with open(mapping_path, encoding="utf-8") as f:
                mapping = yaml.safe_load(f) or {}

            # 컴포지션별 필드 매핑 추출
            compositions = mapping.get("compositions", {})
            for comp_name, comp_config in compositions.items():
                field_mappings = comp_config.get("field_mappings", {})
                template._field_mappings[comp_name] = field_mappings

            logger.debug(
                f"[ConfigStore] 매핑 로드 완료: {template.name}, "
                f"{len(template._field_mappings)}개 컴포지션"
            )

        except Exception as e:
            logger.error(f"[ConfigStore] 매핑 파일 로드 실패: {mapping_path} - {e}")

    def get_template(self, name: str) -> TemplateConfig | None:
        """템플릿 설정 조회"""
        return self._templates.get(name)

    def get_all_templates(self) -> dict[str, TemplateConfig]:
        """모든 템플릿 설정 조회"""
        return self._templates.copy()

    def get_layer_mapping(
        self, template_name: str, comp_name: str, gfx_field: str
    ) -> str | None:
        """GFX 필드명 → AEP 레이어명 변환

        Args:
            template_name: 템플릿 이름
            comp_name: 컴포지션 이름
            gfx_field: GFX 필드명

        Returns:
            AEP 레이어명 또는 None (매핑 없음)
        """
        template = self._templates.get(template_name)
        if not template:
            return None

        field_mappings = template.get_field_mapping(comp_name)
        return field_mappings.get(gfx_field)

    def map_api_to_db(self, api_data: dict[str, Any]) -> dict[str, Any]:
        """API 요청 데이터를 DB 컬럼으로 변환"""
        return self._db_schema.map_fields(api_data)

    def on_reload(self, callback: Callable) -> None:
        """리로드 콜백 등록"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable) -> None:
        """리로드 콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @property
    def version(self) -> str:
        """설정 버전"""
        return self._version


class ConfigWatcher:
    """파일 시스템 감시 기반 핫 리로드

    watchdog 라이브러리를 사용하여 설정 파일 변경을 감지하고
    자동으로 ConfigStore를 리로드합니다.

    사용법:
        ```python
        store = ConfigStore()
        watcher = ConfigWatcher(store, ["config/*.yaml", "config/mappings/*.yaml"])
        watcher.start()

        # 앱 종료 시
        watcher.stop()
        ```
    """

    def __init__(
        self,
        config_store: ConfigStore,
        watch_paths: list[str],
        debounce_seconds: float = 2.0,
    ):
        """
        Args:
            config_store: ConfigStore 인스턴스
            watch_paths: 감시할 파일 경로 패턴 목록
            debounce_seconds: 디바운스 시간 (초)
        """
        self.config_store = config_store
        self.watch_paths = watch_paths
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._debounce_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """파일 감시 시작"""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.warning(
                "[ConfigWatcher] watchdog 미설치 - 핫 리로드 비활성화. "
                "설치: pip install watchdog"
            )
            return

        self._loop = asyncio.get_event_loop()

        class Handler(FileSystemEventHandler):
            def __init__(handler_self, watcher: "ConfigWatcher"):
                handler_self.watcher = watcher

            def on_modified(handler_self, event):
                if event.is_directory:
                    return
                if event.src_path.endswith((".yaml", ".yml", ".json")):
                    logger.debug(f"[ConfigWatcher] 파일 변경 감지: {event.src_path}")
                    handler_self.watcher._schedule_reload()

        handler = Handler(self)
        self._observer = Observer()

        # 감시 경로 등록
        watched_dirs = set()
        for path_pattern in self.watch_paths:
            dir_path = Path(path_pattern).parent
            if dir_path.exists() and str(dir_path) not in watched_dirs:
                self._observer.schedule(handler, str(dir_path), recursive=False)
                watched_dirs.add(str(dir_path))

        self._observer.start()
        logger.info(f"[ConfigWatcher] 파일 감시 시작: {list(watched_dirs)}")

    def stop(self) -> None:
        """파일 감시 중지"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("[ConfigWatcher] 파일 감시 중지")

    def _schedule_reload(self) -> None:
        """디바운스 후 리로드 스케줄"""
        if self._debounce_task:
            self._debounce_task.cancel()

        if self._loop:
            self._debounce_task = self._loop.create_task(self._debounced_reload())

    async def _debounced_reload(self) -> None:
        """디바운스 후 리로드 실행"""
        try:
            await asyncio.sleep(self.debounce_seconds)
            logger.info("[ConfigWatcher] 설정 리로드 실행")
            await self.config_store.reload(self.config_store._config_path)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ConfigWatcher] 리로드 실패: {e}")
