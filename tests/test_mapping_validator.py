"""
MappingValidator 테스트

GFX 데이터와 매핑 파일 간의 검증 로직을 테스트합니다.
"""

import pytest

from lib.mapping_loader import MappingLoader
from lib.mapping_validator import MappingValidator, ValidationResult


@pytest.fixture
def mapping_loader() -> MappingLoader:
    """테스트용 MappingLoader 인스턴스"""
    return MappingLoader()


@pytest.fixture
def validator(mapping_loader: MappingLoader) -> MappingValidator:
    """테스트용 MappingValidator 인스턴스"""
    return MappingValidator(mapping_loader)


class TestValidationResult:
    """ValidationResult 데이터클래스 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.matched_fields == []
        assert result.missing_fields == []
        assert result.fallback_fields == []
        assert result.warnings == []
        assert result.errors == []

    def test_with_errors_is_invalid(self) -> None:
        """에러가 있으면 유효하지 않음"""
        result = ValidationResult(
            is_valid=False,
            errors=["Composition not found"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 1


class TestMappingValidator:
    """MappingValidator 클래스 테스트"""

    def test_validate_valid_gfx_data(self, validator: MappingValidator) -> None:
        """유효한 GFX 데이터 검증"""
        gfx_data = {
            "single_fields": {
                "event_name": "WSOP SUPER CIRCUIT CYPRUS",
                "tournament_name": "EVENT #12",
            },
        }

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="1-Hand-for-hand play is currently in progress",
            gfx_data=gfx_data,
        )

        assert result.is_valid is True
        assert "event_name" in result.matched_fields
        assert "tournament_name" in result.matched_fields

    def test_validate_with_unmapped_fields(self, validator: MappingValidator) -> None:
        """매핑되지 않은 필드 포함 GFX 데이터 검증"""
        gfx_data = {
            "single_fields": {
                "event_name": "WSOP",
                "unknown_field": "value",  # 매핑 없음
            },
        }

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="1-Hand-for-hand play is currently in progress",
            gfx_data=gfx_data,
        )

        assert result.is_valid is True  # 경고만, 차단 없음
        assert "unknown_field" in result.fallback_fields
        assert len(result.warnings) > 0

    def test_validate_nonexistent_composition(self, validator: MappingValidator) -> None:
        """존재하지 않는 컴포지션 검증"""
        gfx_data = {"single_fields": {"event_name": "Test"}}

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="NonExistentComposition",
            gfx_data=gfx_data,
        )

        assert result.is_valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_validate_nonexistent_template(self, validator: MappingValidator) -> None:
        """존재하지 않는 템플릿 검증"""
        gfx_data = {"single_fields": {"event_name": "Test"}}

        result = validator.validate(
            template_name="NonExistentTemplate",
            composition_name="SomeComposition",
            gfx_data=gfx_data,
        )

        assert result.is_valid is False
        assert any("template" in e.lower() or "not found" in e.lower() for e in result.errors)

    def test_validate_with_slots(self, validator: MappingValidator) -> None:
        """슬롯 포함 GFX 데이터 검증"""
        gfx_data = {
            "slots": [
                {"slot_index": 1, "fields": {"name": "PHIL IVEY", "chips": "250,000"}},
                {"slot_index": 2, "fields": {"name": "DANIEL NEGREANU", "chips": "180,000"}},
            ],
            "single_fields": {
                "table_name": "leaderboard final table",
                "event_name": "WSOP",
            },
        }

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="_Feature Table Leaderboard",
            gfx_data=gfx_data,
        )

        # 슬롯 필드가 올바르게 추출되었는지 확인
        assert result.is_valid is True
        assert "slot1_name" in result.matched_fields or "slot1_name" in result.fallback_fields

    def test_extract_gfx_fields_single_fields_only(
        self, validator: MappingValidator
    ) -> None:
        """single_fields만 있는 GFX 데이터에서 필드 추출"""
        gfx_data = {
            "single_fields": {
                "event_name": "WSOP",
                "tournament_name": "Event #12",
            },
        }

        fields = validator._extract_gfx_fields(gfx_data)
        assert "event_name" in fields
        assert "tournament_name" in fields
        assert len(fields) == 2

    def test_extract_gfx_fields_with_slots(self, validator: MappingValidator) -> None:
        """슬롯 포함 GFX 데이터에서 필드 추출"""
        gfx_data = {
            "slots": [
                {"slot_index": 1, "fields": {"name": "PHIL IVEY", "chips": "250,000"}},
                {"slot_index": 2, "fields": {"name": "DANIEL", "chips": "180,000"}},
            ],
            "single_fields": {
                "event_name": "WSOP",
            },
        }

        fields = validator._extract_gfx_fields(gfx_data)
        assert "event_name" in fields
        assert "slot1_name" in fields
        assert "slot1_chips" in fields
        assert "slot2_name" in fields
        assert "slot2_chips" in fields
        assert len(fields) == 5

    def test_validate_empty_gfx_data(self, validator: MappingValidator) -> None:
        """빈 GFX 데이터 검증"""
        gfx_data: dict = {}

        result = validator.validate(
            template_name="CyprusDesign",
            composition_name="1-Hand-for-hand play is currently in progress",
            gfx_data=gfx_data,
        )

        # 빈 데이터는 유효하지만 경고
        assert result.is_valid is True
        assert len(result.warnings) > 0


class TestCompositionExists:
    """컴포지션 존재 확인 테스트"""

    def test_composition_exists(self, validator: MappingValidator) -> None:
        """존재하는 컴포지션 확인"""
        exists = validator.composition_exists(
            "CyprusDesign",
            "1-Hand-for-hand play is currently in progress",
        )
        assert exists is True

    def test_composition_not_exists(self, validator: MappingValidator) -> None:
        """존재하지 않는 컴포지션 확인"""
        exists = validator.composition_exists(
            "CyprusDesign",
            "NonExistentComposition",
        )
        assert exists is False

    def test_template_not_exists(self, validator: MappingValidator) -> None:
        """존재하지 않는 템플릿 확인"""
        exists = validator.composition_exists(
            "NonExistentTemplate",
            "SomeComposition",
        )
        assert exists is False
