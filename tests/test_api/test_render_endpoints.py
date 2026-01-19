"""
렌더링 API 엔드포인트 테스트
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# FastAPI 테스트 클라이언트
try:
    from httpx import ASGITransport, AsyncClient
except ImportError:
    pytest.skip("httpx 미설치", allow_module_level=True)


@pytest.fixture
def mock_supabase_client():
    """Supabase 클라이언트 Mock"""
    client = AsyncMock()
    client.get_pending_count = AsyncMock(return_value=5)
    client.insert_job = AsyncMock(return_value={"id": "test-job-id"})
    client.get_job = AsyncMock(
        return_value={
            "id": "test-job-id",
            "status": "pending",
            "progress": 0,
            "aep_project": "/app/templates/Test.aep",
            "aep_comp_name": "TestComp",
            "gfx_data": {},
            "output_format": "mp4",
            "priority": 100,
            "render_type": "custom",
            "metadata": {},
        }
    )
    client.list_jobs = AsyncMock(
        return_value={
            "items": [],
            "total": 0,
        }
    )
    client.update_job_status = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_config_store():
    """ConfigStore Mock"""
    store = MagicMock()
    store._version = "1.0.0"
    store._templates = {}
    return store


@pytest.fixture
async def app_client(mock_supabase_client, mock_config_store):
    """테스트용 API 클라이언트"""
    from api.dependencies import set_config_store, set_supabase_client
    from api.server import create_app

    # Mock 주입
    set_supabase_client(mock_supabase_client)
    set_config_store(mock_config_store)

    app = create_app(debug=True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "dev-api-key-change-in-production"},
    ) as client:
        yield client


class TestHealthEndpoints:
    """헬스체크 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_check(self, app_client):
        """기본 헬스체크"""
        response = await app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_liveness(self, app_client):
        """Liveness 체크"""
        response = await app_client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRenderEndpoints:
    """렌더링 API 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_submit_render(self, app_client, mock_supabase_client):
        """렌더링 작업 제출"""
        response = await app_client.post(
            "/api/v1/render",
            json={
                "aep_project": "/app/templates/CyprusDesign/CyprusDesign.aep",
                "aep_comp_name": "1-Hand-for-hand play is currently in progress",
                "gfx_data": {"single_fields": {"event_name": "TEST EVENT"}},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

        # DB 호출 확인
        mock_supabase_client.insert_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_render_with_options(self, app_client, mock_supabase_client):
        """렌더링 작업 제출 (옵션 포함)"""
        response = await app_client.post(
            "/api/v1/render",
            json={
                "aep_project": "/app/templates/Test.aep",
                "aep_comp_name": "Main",
                "gfx_data": {},
                "output_format": "mov_alpha",
                "priority": 10,
                "callback_url": "http://example.com/callback",
                "metadata": {"external_id": "123"},
            },
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_submit_render_missing_fields(self, app_client):
        """필수 필드 누락 시 에러"""
        response = await app_client.post(
            "/api/v1/render",
            json={
                "aep_project": "/app/templates/Test.aep",
                # aep_comp_name 누락
                "gfx_data": {},
            },
        )

        assert response.status_code == 422  # Validation Error

    @pytest.mark.asyncio
    async def test_get_render_status(self, app_client, mock_supabase_client):
        """렌더링 상태 조회"""
        response = await app_client.get("/api/v1/render/test-job-id/status")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-job-id"
        assert data["status"] == "pending"
        assert "progress" in data

    @pytest.mark.asyncio
    async def test_get_render_not_found(self, app_client, mock_supabase_client):
        """존재하지 않는 작업 조회"""
        mock_supabase_client.get_job = AsyncMock(return_value=None)

        response = await app_client.get("/api/v1/render/nonexistent-id/status")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_render_detail(self, app_client, mock_supabase_client):
        """렌더링 상세 정보 조회"""
        response = await app_client.get("/api/v1/render/test-job-id")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-job-id"
        assert "aep_project" in data
        assert "aep_comp_name" in data

    @pytest.mark.asyncio
    async def test_cancel_render(self, app_client, mock_supabase_client):
        """렌더링 작업 취소"""
        response = await app_client.delete("/api/v1/render/test-job-id")

        assert response.status_code == 204
        mock_supabase_client.update_job_status.assert_called_once_with(
            "test-job-id", "cancelled"
        )

    @pytest.mark.asyncio
    async def test_cancel_completed_render(self, app_client, mock_supabase_client):
        """이미 완료된 작업 취소 시도"""
        mock_supabase_client.get_job = AsyncMock(
            return_value={
                "id": "test-job-id",
                "status": "completed",
            }
        )

        response = await app_client.delete("/api/v1/render/test-job-id")

        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["error"] == "INVALID_STATE"

    @pytest.mark.asyncio
    async def test_list_renders(self, app_client, mock_supabase_client):
        """렌더링 작업 목록 조회"""
        mock_supabase_client.list_jobs = AsyncMock(
            return_value={
                "items": [
                    {"id": "job-1", "status": "pending", "progress": 0, "metadata": {}},
                    {
                        "id": "job-2",
                        "status": "rendering",
                        "progress": 50,
                        "metadata": {},
                    },
                ],
                "total": 2,
            }
        )

        response = await app_client.get("/api/v1/render")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_renders_with_filter(self, app_client, mock_supabase_client):
        """필터링 조회"""
        response = await app_client.get(
            "/api/v1/render?status=pending&page=1&page_size=10"
        )

        assert response.status_code == 200
        mock_supabase_client.list_jobs.assert_called_once()


class TestBatchRenderEndpoints:
    """배치 렌더링 API 테스트"""

    @pytest.mark.asyncio
    async def test_submit_batch_render(self, app_client, mock_supabase_client):
        """배치 렌더링 제출"""
        response = await app_client.post(
            "/api/v1/render/batch",
            json={
                "jobs": [
                    {
                        "aep_project": "/app/templates/Test.aep",
                        "aep_comp_name": "Comp1",
                        "gfx_data": {},
                    },
                    {
                        "aep_project": "/app/templates/Test.aep",
                        "aep_comp_name": "Comp2",
                        "gfx_data": {},
                    },
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["accepted"] == 2
        assert data["rejected"] == 0
        assert len(data["jobs"]) == 2


class TestAuthMiddleware:
    """인증 미들웨어 테스트"""

    @pytest.mark.asyncio
    async def test_missing_api_key(self, mock_supabase_client, mock_config_store):
        """API Key 누락"""
        from api.dependencies import set_config_store, set_supabase_client
        from api.server import create_app

        set_supabase_client(mock_supabase_client)
        set_config_store(mock_config_store)

        app = create_app(debug=True)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            # X-API-Key 헤더 없음
        ) as client:
            response = await client.get("/api/v1/render")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "MISSING_API_KEY"

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, mock_supabase_client, mock_config_store):
        """잘못된 API Key"""
        from api.dependencies import set_config_store, set_supabase_client
        from api.server import create_app

        set_supabase_client(mock_supabase_client)
        set_config_store(mock_config_store)

        app = create_app(debug=True)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": "invalid-key"},
        ) as client:
            response = await client.get("/api/v1/render")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "INVALID_API_KEY"
