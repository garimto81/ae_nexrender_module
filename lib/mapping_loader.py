"""
AEP 템플릿별 레이어 매핑 로더

GFX JSON 필드명과 AEP 레이어명 간의 매핑을 관리합니다.

설계 원칙:
- GFX 스키마는 고정 (변경 불가)
- AEP 파일은 자주 변경될 수 있음
- 매핑 설정 파일만 수정하여 동기화
"""

import json
from pathlib import Path
from typing import Any

import yaml


class MappingLoader:
    """AEP 템플릿별 레이어 매핑 로더

    YAML 또는 JSON 형식의 매핑 설정 파일을 로드하여
    GFX 필드명을 AEP 레이어명으로 변환합니다.

    사용 예시:
        loader = MappingLoader()
        layer_name = loader.get_layer_name(
            "CyprusDesign",
            "1-Hand-for-hand play is currently in progress",
            "event_name"
        )
        # 결과: "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE"
    """

    DEFAULT_MAPPINGS_DIR = "config/mappings"

    def __init__(self, mappings_dir: str | None = None):
        """
        Args:
            mappings_dir: 매핑 설정 파일 디렉토리 경로
                기본값: config/mappings (프로젝트 루트 기준)
        """
        if mappings_dir:
            self.mappings_dir = Path(mappings_dir)
        else:
            # 프로젝트 루트 기준 기본 경로
            project_root = Path(__file__).parent.parent
            self.mappings_dir = project_root / self.DEFAULT_MAPPINGS_DIR

        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, template_name: str) -> dict[str, Any]:
        """매핑 설정 파일 로드

        YAML 파일 우선, JSON 파일 폴백.
        로드된 설정은 메모리에 캐시됩니다.

        Args:
            template_name: AEP 템플릿 이름 (확장자 제외)

        Returns:
            매핑 설정 딕셔너리 또는 빈 딕셔너리
        """
        if template_name in self._cache:
            return self._cache[template_name]

        mapping: dict[str, Any] = {}

        # YAML 우선
        yaml_path = self.mappings_dir / f"{template_name}.yaml"
        if yaml_path.exists():
            mapping = self._load_yaml(yaml_path)
        else:
            # JSON 폴백
            json_path = self.mappings_dir / f"{template_name}.json"
            if json_path.exists():
                mapping = self._load_json(json_path)

        self._cache[template_name] = mapping
        return mapping

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """YAML 파일 로드"""
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[MappingLoader] YAML 로드 실패: {path} - {e}")
            return {}

    def _load_json(self, path: Path) -> dict[str, Any]:
        """JSON 파일 로드"""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[MappingLoader] JSON 로드 실패: {path} - {e}")
            return {}

    def get_layer_name(
        self,
        template_name: str,
        composition_name: str,
        gfx_field: str,
    ) -> str | None:
        """GFX 필드명 → AEP 레이어명 변환

        매핑 설정에서 해당 컴포지션의 필드 매핑을 조회합니다.
        매핑이 없으면 None을 반환합니다.

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름
            gfx_field: GFX JSON 필드명

        Returns:
            AEP 레이어명 또는 None (매핑 없음)
        """
        mapping = self.load(template_name)
        compositions = mapping.get("compositions", {})
        comp_mapping = compositions.get(composition_name, {})
        field_mappings = comp_mapping.get("field_mappings", {})

        return field_mappings.get(gfx_field)

    def get_all_field_mappings(
        self,
        template_name: str,
        composition_name: str,
    ) -> dict[str, str]:
        """컴포지션의 전체 필드 매핑 조회

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            {gfx_field: layer_name} 딕셔너리
        """
        mapping = self.load(template_name)
        compositions = mapping.get("compositions", {})
        comp_mapping = compositions.get(composition_name, {})

        return comp_mapping.get("field_mappings", {})

    def get_compositions(self, template_name: str) -> list[str]:
        """템플릿의 모든 컴포지션 목록 조회

        Args:
            template_name: AEP 템플릿 이름

        Returns:
            컴포지션 이름 리스트
        """
        mapping = self.load(template_name)
        return list(mapping.get("compositions", {}).keys())

    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._cache.clear()

    def reload(self, template_name: str) -> dict[str, Any]:
        """매핑 설정 강제 리로드

        Args:
            template_name: AEP 템플릿 이름

        Returns:
            새로 로드된 매핑 설정
        """
        if template_name in self._cache:
            del self._cache[template_name]
        return self.load(template_name)

    def list_all_templates(self) -> list[str]:
        """모든 템플릿 이름 목록 조회

        Returns:
            템플릿 이름 리스트 (매핑 파일 기준)
        """
        templates: list[str] = []

        if self.mappings_dir.exists():
            # YAML 파일
            for mapping_file in self.mappings_dir.glob("*.yaml"):
                templates.append(mapping_file.stem)

            # JSON 파일 (YAML 없는 경우)
            for mapping_file in self.mappings_dir.glob("*.json"):
                if mapping_file.stem not in templates:
                    templates.append(mapping_file.stem)

        return sorted(templates)

    def list_all_compositions(self) -> dict[str, list[str]]:
        """모든 템플릿의 컴포지션 목록 조회

        Returns:
            {template_name: [composition_names]} 딕셔너리
        """
        result: dict[str, list[str]] = {}

        for template_name in self.list_all_templates():
            result[template_name] = self.get_compositions(template_name)

        return result

    def get_composition_metadata(
        self,
        template_name: str,
        composition_name: str,
    ) -> dict[str, Any] | None:
        """컴포지션 메타데이터 조회

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            메타데이터 딕셔너리 또는 None
        """
        mapping = self.load(template_name)
        compositions = mapping.get("compositions", {})
        comp_data = compositions.get(composition_name)

        if not comp_data:
            return None

        return {
            "description": comp_data.get("description"),
            "field_count": len(comp_data.get("field_mappings", {})),
            "layer_info": comp_data.get("layer_info"),
        }


def extract_template_name(aep_path: str) -> str:
    """AEP 파일 경로에서 템플릿 이름 추출

    Args:
        aep_path: AEP 파일 경로 (예: C:/templates/CyprusDesign/CyprusDesign.aep)

    Returns:
        템플릿 이름 (예: CyprusDesign)
    """
    path = Path(aep_path)
    return path.stem  # 확장자 제외한 파일명
