"""
Nexrender 클라이언트 테스트

httpx mock을 사용하여 실제 서버 없이 클라이언트 동작을 검증합니다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lib.client import NexrenderClient, NexrenderSyncClient
from lib.errors import NexrenderError


class TestNexrenderClientInit:
    """NexrenderClient 초기화 테스트"""

    def test_init_default(self):
        """기본값으로 초기화"""
        client = NexrenderClient(base_url="http://localhost:3000")

        assert client.base_url == "http://localhost:3000"
        assert client.secret is None
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_init_with_secret(self):
        """secret 포함 초기화"""
        client = NexrenderClient(
            base_url="http://localhost:3000",
            secret="my-secret",
            timeout=60.0,
            max_retries=5,
        )

        assert client.secret == "my-secret"
        assert client.timeout == 60.0
        assert client.max_retries == 5

    def test_create_client_without_secret(self):
        """secret 없이 HTTP 클라이언트 생성"""
        client = NexrenderClient(base_url="http://localhost:3000")
        http_client = client._create_client()

        assert http_client.base_url == httpx.URL("http://localhost:3000")
        assert "nexrender-secret" not in http_client.headers

    def test_create_client_with_secret(self):
        """secret 포함 HTTP 클라이언트 생성"""
        client = NexrenderClient(
            base_url="http://localhost:3000",
            secret="my-secret",
        )
        http_client = client._create_client()

        assert http_client.headers.get("nexrender-secret") == "my-secret"


class TestNexrenderClientAsync:
    """NexrenderClient 비동기 메서드 테스트"""

    @pytest.fixture
    def client(self) -> NexrenderClient:
        """테스트용 클라이언트"""
        return NexrenderClient(
            base_url="http://localhost:3000",
            secret="test-secret",
        )

    @pytest.mark.asyncio
    async def test_close(self, client: NexrenderClient):
        """close 메서드 (no-op)"""
        # close는 no-op이므로 예외 없이 실행되면 성공
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: NexrenderClient):
        """헬스 체크 성공"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.health_check()

            assert result is True
            mock_http_client.get.assert_called_once_with("/api/v1/jobs")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client: NexrenderClient):
        """헬스 체크 실패 (서버 오류)"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client: NexrenderClient):
        """헬스 체크 연결 오류"""
        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_submit_job_success(self, client: NexrenderClient):
        """작업 제출 성공"""
        job_data = {"template": {"src": "file://test.aep"}}
        response_data = {"uid": "job-123", "state": "queued"}

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.submit_job(job_data)

            assert result == response_data
            mock_http_client.post.assert_called_once_with("/api/v1/jobs", json=job_data)

    @pytest.mark.asyncio
    async def test_submit_job_http_error(self, client: NexrenderClient):
        """작업 제출 HTTP 오류"""
        job_data = {"template": {"src": "file://test.aep"}}

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad Request",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="작업 제출 실패"):
                await client.submit_job(job_data)

    @pytest.mark.asyncio
    async def test_submit_job_connection_error(self, client: NexrenderClient):
        """작업 제출 연결 오류"""
        job_data = {"template": {"src": "file://test.aep"}}

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="Nexrender 서버 연결 실패"):
                await client.submit_job(job_data)

    @pytest.mark.asyncio
    async def test_get_job_success(self, client: NexrenderClient):
        """작업 조회 성공"""
        response_data = {"uid": "job-123", "state": "finished", "renderProgress": 1.0}

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.get_job("job-123")

            assert result == response_data
            mock_http_client.get.assert_called_once_with("/api/v1/jobs/job-123")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: NexrenderClient):
        """작업 조회 - 404"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="작업을 찾을 수 없습니다"):
                await client.get_job("nonexistent-job")

    @pytest.mark.asyncio
    async def test_list_jobs_success(self, client: NexrenderClient):
        """작업 목록 조회 성공"""
        response_data = [
            {"uid": "job-1", "state": "finished"},
            {"uid": "job-2", "state": "queued"},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.list_jobs()

            assert result == response_data

    @pytest.mark.asyncio
    async def test_list_jobs_error(self, client: NexrenderClient):
        """작업 목록 조회 오류"""
        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="작업 목록 조회 실패"):
                await client.list_jobs()

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, client: NexrenderClient):
        """작업 취소 성공"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.delete = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.cancel_job("job-123")

            assert result is True
            mock_http_client.delete.assert_called_once_with("/api/v1/jobs/job-123")

    @pytest.mark.asyncio
    async def test_cancel_job_204(self, client: NexrenderClient):
        """작업 취소 성공 (204 응답)"""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.delete = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.cancel_job("job-123")

            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_job_failure(self, client: NexrenderClient):
        """작업 취소 실패"""
        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = AsyncMock()
            mock_http_client.delete = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = await client.cancel_job("job-123")

            assert result is False


class TestNexrenderClientPollUntilComplete:
    """poll_until_complete 메서드 테스트"""

    @pytest.fixture
    def client(self) -> NexrenderClient:
        """테스트용 클라이언트"""
        return NexrenderClient(base_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_poll_until_complete_success(self, client: NexrenderClient):
        """폴링 성공 (즉시 완료)"""
        with patch.object(client, "get_job") as mock_get_job:
            mock_get_job.return_value = {
                "uid": "job-123",
                "state": "finished",
                "renderProgress": 1.0,
            }

            result = await client.poll_until_complete("job-123", poll_interval=0)

            assert result["state"] == "finished"
            mock_get_job.assert_called_once_with("job-123")

    @pytest.mark.asyncio
    async def test_poll_until_complete_with_callback(self, client: NexrenderClient):
        """폴링 성공 (콜백 호출)"""
        callback_calls: list[tuple[int, str]] = []

        def callback(progress: int, state: str):
            callback_calls.append((progress, state))

        with patch.object(client, "get_job") as mock_get_job:
            mock_get_job.return_value = {
                "uid": "job-123",
                "state": "finished",
                "renderProgress": 1.0,
            }

            await client.poll_until_complete("job-123", callback=callback, poll_interval=0)

            assert len(callback_calls) == 1
            assert callback_calls[0] == (100, "finished")

    @pytest.mark.asyncio
    async def test_poll_until_complete_error_state(self, client: NexrenderClient):
        """폴링 실패 (에러 상태)"""
        with patch.object(client, "get_job") as mock_get_job:
            mock_get_job.return_value = {
                "uid": "job-123",
                "state": "error",
                "error": "AE crashed",
            }

            with pytest.raises(NexrenderError, match="렌더링 실패: AE crashed"):
                await client.poll_until_complete("job-123", poll_interval=0)

    @pytest.mark.asyncio
    async def test_poll_until_complete_timeout(self, client: NexrenderClient):
        """폴링 타임아웃"""
        with patch.object(client, "get_job") as mock_get_job:
            mock_get_job.return_value = {
                "uid": "job-123",
                "state": "rendering",
                "renderProgress": 0.5,
            }

            with pytest.raises(TimeoutError, match="렌더링 타임아웃"):
                await client.poll_until_complete(
                    "job-123",
                    timeout=1,
                    poll_interval=1,
                )


class TestNexrenderSyncClient:
    """NexrenderSyncClient 동기 클라이언트 테스트"""

    @pytest.fixture
    def client(self) -> NexrenderSyncClient:
        """테스트용 동기 클라이언트"""
        return NexrenderSyncClient(
            base_url="http://localhost:3000",
            secret="test-secret",
        )

    def test_init(self, client: NexrenderSyncClient):
        """동기 클라이언트 초기화"""
        assert client.base_url == "http://localhost:3000"
        assert client.secret == "test-secret"
        assert client.timeout == 30.0

    def test_create_client_with_secret(self, client: NexrenderSyncClient):
        """secret 포함 HTTP 클라이언트 생성"""
        http_client = client._create_client()

        assert http_client.headers.get("nexrender-secret") == "test-secret"

    def test_submit_job_success(self, client: NexrenderSyncClient):
        """동기 작업 제출 성공"""
        job_data = {"template": {"src": "file://test.aep"}}
        response_data = {"uid": "job-123", "state": "queued"}

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = MagicMock()
            mock_http_client.post.return_value = mock_response
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = client.submit_job(job_data)

            assert result == response_data

    def test_submit_job_http_error(self, client: NexrenderSyncClient):
        """동기 작업 제출 HTTP 오류"""
        job_data = {"template": {"src": "file://test.aep"}}

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = MagicMock()
            mock_http_client.post.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=mock_response,
            )
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="작업 제출 실패"):
                client.submit_job(job_data)

    def test_get_job_success(self, client: NexrenderSyncClient):
        """동기 작업 조회 성공"""
        response_data = {"uid": "job-123", "state": "finished"}

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = mock_response
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_create.return_value = mock_http_client

            result = client.get_job("job-123")

            assert result == response_data

    def test_get_job_not_found(self, client: NexrenderSyncClient):
        """동기 작업 조회 - 404"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = MagicMock()
            mock_http_client.get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="작업을 찾을 수 없습니다"):
                client.get_job("nonexistent-job")

    def test_get_job_connection_error(self, client: NexrenderSyncClient):
        """동기 작업 조회 연결 오류"""
        with patch.object(client, "_create_client") as mock_create:
            mock_http_client = MagicMock()
            mock_http_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_create.return_value = mock_http_client

            with pytest.raises(NexrenderError, match="Nexrender 서버 연결 실패"):
                client.get_job("job-123")
