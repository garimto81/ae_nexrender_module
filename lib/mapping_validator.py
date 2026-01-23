"""
GFX 데이터와 매핑 파일 간의 검증 로직

GFX 데이터가 매핑 파일과 일치하는지 확인하고,
누락된 필드, fallback 필드 등을 분류합니다.
"""

from dataclasses import dataclass, field
from typing import Any

from .mapping_loader import MappingLoader


@dataclass
class ValidationResult:
    """매핑 검증 결과

    Attributes:
        is_valid: 검증 통과 여부 (치명적 에러 없음)
        matched_fields: 매핑 파일에 정의된 필드 목록
        missing_fields: GFX 데이터에 없는 필드 목록 (매핑에서 요구하는 필드)
        fallback_fields: 매핑 없이 원본 필드명 사용하는 필드 목록
        warnings: 경고 메시지 목록 (차단하지 않음)
        errors: 에러 메시지 목록 (치명적 오류)
    """

    is_valid: bool = True
    matched_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    fallback_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MappingValidator:
    """GFX 데이터와 매핑 파일 검증기

    GFX 데이터가 매핑 파일과 일치하는지 확인하고,
    누락된 필드, fallback 필드 등을 분류합니다.

    사용 예시:
        ```python
        loader = MappingLoader()
        validator = MappingValidator(loader)

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="_Feature Table Leaderboard",
            gfx_data={"single_fields": {"event_name": "WSOP"}}
        )

        if not result.is_valid:
            print(f"Errors: {result.errors}")
        elif result.warnings:
            print(f"Warnings: {result.warnings}")
        ```
    """

    def __init__(self, mapping_loader: MappingLoader) -> None:
        """
        Args:
            mapping_loader: 매핑 파일 로더 인스턴스
        """
        self.mapping_loader = mapping_loader

    def validate(
        self,
        template_name: str,
        composition_name: str,
        gfx_data: dict[str, Any],
    ) -> ValidationResult:
        """GFX 데이터와 매핑 파일 검증

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름
            gfx_data: GFX 데이터 (slots, single_fields 포함)

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult()

        # 1. 템플릿/매핑 파일 존재 확인
        mapping = self.mapping_loader.load(template_name)
        if not mapping:
            result.is_valid = False
            result.errors.append(
                f"Template '{template_name}' mapping file not found"
            )
            return result

        # 2. 컴포지션 존재 확인
        compositions = mapping.get("compositions", {})
        if composition_name not in compositions:
            result.is_valid = False
            result.errors.append(
                f"Composition '{composition_name}' not found in template '{template_name}'"
            )
            return result

        # 3. GFX 데이터에서 필드 추출
        gfx_fields = self._extract_gfx_fields(gfx_data)

        if not gfx_fields:
            result.warnings.append("GFX data is empty or has no fields")
            return result

        # 4. 매핑 정보 조회
        comp_mapping = compositions.get(composition_name, {})
        field_mappings = comp_mapping.get("field_mappings", {})

        # 5. 필드 분류
        for gfx_field in gfx_fields:
            if gfx_field in field_mappings:
                # 매핑 파일에 정의된 필드
                result.matched_fields.append(gfx_field)
            else:
                # 매핑 없음 → fallback (원본 필드명 사용)
                result.fallback_fields.append(gfx_field)
                result.warnings.append(
                    f"Field '{gfx_field}' not in mapping, using fallback (original field name)"
                )

        # 6. 매핑에는 있지만 GFX 데이터에 없는 필드 찾기 (선택적)
        for mapping_field in field_mappings:
            if mapping_field not in gfx_fields:
                result.missing_fields.append(mapping_field)

        # missing_fields는 경고만 (필수가 아닐 수 있음)
        if result.missing_fields:
            result.warnings.append(
                f"Mapping fields not in GFX data: {result.missing_fields}"
            )

        return result

    def _extract_gfx_fields(self, gfx_data: dict[str, Any]) -> set[str]:
        """GFX 데이터에서 모든 필드명 추출

        Args:
            gfx_data: GFX 데이터

        Returns:
            필드명 집합 (single_fields 키 + slot{N}_{field} 형태)
        """
        fields: set[str] = set()

        # single_fields 추출
        single_fields = gfx_data.get("single_fields", {})
        fields.update(single_fields.keys())

        # slots 추출 (slot{N}_{field} 형태로 변환)
        slots = gfx_data.get("slots", [])
        for slot in slots:
            slot_index = slot.get("slot_index", 0)
            slot_fields = slot.get("fields", {})

            for field_name in slot_fields:
                # slot1_name, slot2_chips 형태로 변환
                prefixed_field = f"slot{slot_index}_{field_name}"
                fields.add(prefixed_field)

        return fields

    def composition_exists(
        self,
        template_name: str,
        composition_name: str,
    ) -> bool:
        """컴포지션 존재 여부 확인

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            컴포지션 존재 여부
        """
        mapping = self.mapping_loader.load(template_name)
        if not mapping:
            return False

        compositions = mapping.get("compositions", {})
        return composition_name in compositions

    def get_composition_info(
        self,
        template_name: str,
        composition_name: str,
    ) -> dict[str, Any] | None:
        """컴포지션 정보 조회

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            컴포지션 정보 딕셔너리 또는 None
        """
        mapping = self.mapping_loader.load(template_name)
        if not mapping:
            return None

        compositions = mapping.get("compositions", {})
        return compositions.get(composition_name)

    def get_slot_count(
        self,
        template_name: str,
        composition_name: str,
    ) -> int:
        """컴포지션의 슬롯 수 계산

        field_mappings에서 slot{N}_ 패턴을 찾아 최대 슬롯 번호를 반환합니다.

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            슬롯 수 (0부터)
        """
        info = self.get_composition_info(template_name, composition_name)
        if not info:
            return 0

        field_mappings = info.get("field_mappings", {})
        max_slot = 0

        for field_name in field_mappings:
            if field_name.startswith("slot"):
                # slot1_name → 1 추출
                try:
                    parts = field_name.split("_", 1)
                    slot_num = int(parts[0].replace("slot", ""))
                    max_slot = max(max_slot, slot_num)
                except (ValueError, IndexError):
                    pass

        return max_slot

    def get_single_field_count(
        self,
        template_name: str,
        composition_name: str,
    ) -> int:
        """컴포지션의 단일 필드 수 계산

        field_mappings에서 slot{N}_ 패턴이 아닌 필드 수를 반환합니다.

        Args:
            template_name: AEP 템플릿 이름
            composition_name: 컴포지션 이름

        Returns:
            단일 필드 수
        """
        info = self.get_composition_info(template_name, composition_name)
        if not info:
            return 0

        field_mappings = info.get("field_mappings", {})
        count = 0

        for field_name in field_mappings:
            if not field_name.startswith("slot"):
                count += 1

        return count
