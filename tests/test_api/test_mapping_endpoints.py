"""
매핑 API 엔드포인트 테스트

/api/v1/mapping API의 통합 테스트입니다.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from api.dependencies import set_config_store, set_supabase_client
from api.server import create_app


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase 클라이언트"""
    client = AsyncMock()
    client.get_pending_count = AsyncMock(return_value=5)
    client.insert_job = AsyncMock(return_value={"id": "test-job-id"})
    return client


@pytest.fixture
def mock_config_store():
    """Mock Config Store"""
    store = MagicMock()
    store._version = "1.0.0"
    store._templates = {}
    return store


@pytest.fixture
async def app_client(mock_supabase_client, mock_config_store):
    """테스트용 FastAPI 앱 클라이언트"""
    set_supabase_client(mock_supabase_client)
    set_config_store(mock_config_store)

    app = create_app(debug=True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "dev-api-key-change-in-production"},
    ) as client:
        yield client


class TestMappingSummaryEndpoint:
    """GET /api/v1/mapping 테스트"""

    @pytest.mark.asyncio
    async def test_get_all_mappings(self, app_client):
        """전체 매핑 상태 요약 조회"""
        response = await app_client.get("/api/v1/mapping")

        assert response.status_code == 200
        data = response.json()
        assert "total_templates" in data
        assert "total_compositions" in data
        assert "templates" in data

    @pytest.mark.asyncio
    async def test_get_all_mappings_includes_cyprus_design(self, app_client):
        """CyprusDesign 템플릿 포함 확인"""
        response = await app_client.get("/api/v1/mapping")

        assert response.status_code == 200
        data = response.json()

        # CyprusDesign 템플릿이 있어야 함
        template_names = [t["template"] for t in data["templates"]]
        assert "CyprusDesign" in template_names


class TestCompositionMappingEndpoint:
    """GET /api/v1/mapping/{template}/{composition} 테스트"""

    @pytest.mark.asyncio
    async def test_get_composition_mapping(self, app_client):
        """컴포지션 매핑 상세 조회"""
        response = await app_client.get(
            "/api/v1/mapping/CyprusDesign/1-Hand-for-hand play is currently in progress"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["template"] == "CyprusDesign"
        assert data["composition"] == "1-Hand-for-hand play is currently in progress"
        assert "field_mappings" in data
        assert "description" in data

    @pytest.mark.asyncio
    async def test_get_composition_mapping_with_slots(self, app_client):
        """슬롯 포함 컴포지션 매핑 조회"""
        response = await app_client.get(
            "/api/v1/mapping/CyprusDesign/_Feature Table Leaderboard"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["slot_count"] >= 9  # 9인용 리더보드
        assert "slot1_name" in data["field_mappings"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_composition(self, app_client):
        """존재하지 않는 컴포지션 조회 시 404"""
        response = await app_client.get(
            "/api/v1/mapping/CyprusDesign/NonExistentComposition"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "COMPOSITION_NOT_FOUND"
        assert "available_compositions" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, app_client):
        """존재하지 않는 템플릿 조회 시 404"""
        response = await app_client.get(
            "/api/v1/mapping/NonExistentTemplate/SomeComposition"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "MAPPING_NOT_FOUND"


class TestMappingValidationEndpoint:
    """POST /api/v1/mapping/validate 테스트"""

    @pytest.mark.asyncio
    async def test_validate_valid_gfx_data(self, app_client):
        """유효한 GFX 데이터 검증"""
        response = await app_client.post(
            "/api/v1/mapping/validate",
            json={
                "template_name": "CyprusDesign",
                "composition_name": "1-Hand-for-hand play is currently in progress",
                "gfx_data": {
                    "single_fields": {
                        "event_name": "WSOP SUPER CIRCUIT CYPRUS",
                        "tournament_name": "EVENT #12",
                    },
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert "event_name" in data["matched_fields"]

    @pytest.mark.asyncio
    async def test_validate_with_fallback_fields(self, app_client):
        """fallback 필드 포함 GFX 데이터 검증"""
        response = await app_client.post(
            "/api/v1/mapping/validate",
            json={
                "template_name": "CyprusDesign",
                "composition_name": "1-Hand-for-hand play is currently in progress",
                "gfx_data": {
                    "single_fields": {
                        "event_name": "WSOP",
                        "custom_field": "value",  # 매핑 없음
                    },
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True  # 경고만, 차단 없음
        assert "custom_field" in data["fallback_fields"]
        assert len(data["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_validate_nonexistent_composition(self, app_client):
        """존재하지 않는 컴포지션 검증"""
        response = await app_client.post(
            "/api/v1/mapping/validate",
            json={
                "template_name": "CyprusDesign",
                "composition_name": "NonExistentComposition",
                "gfx_data": {"single_fields": {"event_name": "Test"}},
            },
        )

        assert response.status_code == 200  # 검증 결과이므로 200
        data = response.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_with_slots(self, app_client):
        """슬롯 포함 GFX 데이터 검증"""
        response = await app_client.post(
            "/api/v1/mapping/validate",
            json={
                "template_name": "CyprusDesign",
                "composition_name": "_Feature Table Leaderboard",
                "gfx_data": {
                    "slots": [
                        {
                            "slot_index": 1,
                            "fields": {"name": "PHIL IVEY", "chips": "250,000"},
                        },
                    ],
                    "single_fields": {"event_name": "WSOP"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True


class TestRenderValidationIntegration:
    """렌더링 API와 매핑 검증 통합 테스트"""

    @pytest.mark.asyncio
    async def test_render_with_invalid_composition_blocked(
        self, app_client, mock_supabase_client
    ):
        """잘못된 컴포지션으로 렌더링 제출 시 400 에러"""
        response = await app_client.post(
            "/api/v1/render",  # validate_mapping=true (기본값)
            json={
                "aep_project": "/app/templates/CyprusDesign/CyprusDesign.aep",
                "aep_comp_name": "NonExistentComposition",
                "gfx_data": {"single_fields": {"event_name": "Test"}},
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "INVALID_COMPOSITION"
        assert "available_compositions" in data["detail"]

    @pytest.mark.asyncio
    async def test_render_with_valid_composition_passes(
        self, app_client, mock_supabase_client
    ):
        """유효한 컴포지션으로 렌더링 제출 성공"""
        response = await app_client.post(
            "/api/v1/render",
            json={
                "aep_project": "/app/templates/CyprusDesign/CyprusDesign.aep",
                "aep_comp_name": "1-Hand-for-hand play is currently in progress",
                "gfx_data": {
                    "single_fields": {
                        "event_name": "WSOP SUPER CIRCUIT CYPRUS",
                    },
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_render_with_validation_disabled(
        self, app_client, mock_supabase_client
    ):
        """검증 비활성화 시 잘못된 컴포지션도 통과"""
        response = await app_client.post(
            "/api/v1/render?validate_mapping=false",
            json={
                "aep_project": "/app/templates/Test.aep",
                "aep_comp_name": "AnyComposition",
                "gfx_data": {},
            },
        )

        assert response.status_code == 201
