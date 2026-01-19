"""
JobProcessor E2E 통합 테스트

실제 Nexrender 서버 없이 전체 워크플로우를 테스트합니다.
Mock을 사용하여 외부 의존성을 대체합니다.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lib.types import RenderStatus
from worker.config import WorkerConfig
from worker.job_processor import JobProcessor


@pytest.fixture
def mock_supabase_client():
    """Mock SupabaseQueueClient"""
    client = AsyncMock()

    # 기본 반환값 설정
    client.update_job_status = AsyncMock()
    client.update_progress = AsyncMock()
    client.set_nexrender_job_id = AsyncMock()
    client.mark_completed = AsyncMock()
    client.mark_failed = AsyncMock()
    client.get_job = AsyncMock(
        return_value={
            "id": "test-job-id",
            "error_details": {"retry_count": 0, "max_retries": 3},
        }
    )

    return client


@pytest.fixture
def mock_nexrender_client():
    """Mock NexrenderClient"""
    with patch("worker.job_processor.NexrenderClient") as mock_class:
        client = AsyncMock()
        mock_class.return_value = client

        # submit_job 응답
        client.submit_job = AsyncMock(
            return_value={
                "uid": "nexrender-job-uid-123",
                "state": "queued",
            }
        )

        # get_job 응답 시퀀스 (상태 전환)
        client.get_job = AsyncMock(
            side_effect=[
                {"state": "queued", "renderProgress": 0},
                {"state": "started", "renderProgress": 0},
                {"state": "rendering", "renderProgress": 0.3},
                {"state": "rendering", "renderProgress": 0.6},
                {"state": "rendering", "renderProgress": 0.9},
                {"state": "encoding", "renderProgress": 1.0},
                {"state": "finished", "renderProgress": 1.0},
            ]
        )

        yield client


@pytest.fixture
def test_config(tmp_path: Path) -> WorkerConfig:
    """테스트용 WorkerConfig (임시 디렉토리 사용)"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return WorkerConfig(
        supabase_url="https://test.supabase.co",
        supabase_service_key="test_key",
        nexrender_url="http://localhost:3000",
        nexrender_secret="",
        aep_template_dir=str(tmp_path / "templates"),
        output_dir=str(output_dir),
        nas_output_path="",  # NAS 비활성화
        render_timeout=60,
        max_retries=3,
    )


@pytest.fixture
def sample_render_job(test_config: WorkerConfig) -> dict[str, Any]:
    """샘플 렌더링 작업"""
    return {
        "id": "test-job-12345",
        "aep_project": "/app/templates/CyprusDesign/CyprusDesign.aep",
        "aep_comp_name": "Main Composition",
        "output_format": "mp4",
        "output_path": f"{test_config.output_dir}/test-job-12345.mp4",
        "gfx_data": {
            "slots": [
                {"slot_index": 1, "fields": {"name": "Player 1", "chips": "100,000"}}
            ],
            "single_fields": {"table_id": "Table 1", "event_name": "Test Event"},
        },
        "render_type": "custom",
        "priority": 5,
    }


class TestJobProcessorE2E:
    """JobProcessor E2E 테스트"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        mock_nexrender_client,
        sample_render_job: dict[str, Any],
    ):
        """전체 워크플로우 성공 테스트"""
        # 출력 파일 생성 (렌더링 완료 시뮬레이션)
        output_path = Path(sample_render_job["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake video content" * 1000)  # 18KB

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(test_config, mock_supabase_client)
            result = await processor.process(sample_render_job)

        # 결과 검증
        assert result["status"] == "success"
        assert result["job_id"] == "test-job-12345"
        assert "render_duration_ms" in result

        # Supabase 호출 검증
        mock_supabase_client.update_job_status.assert_called()
        mock_supabase_client.set_nexrender_job_id.assert_called_once()
        mock_supabase_client.mark_completed.assert_called_once()

        # 정리
        output_path.unlink()

    @pytest.mark.asyncio
    async def test_nexrender_error_handling(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        sample_render_job: dict[str, Any],
    ):
        """Nexrender 오류 처리 테스트"""
        from lib.errors import NexrenderError

        mock_nexrender = AsyncMock()
        mock_nexrender.submit_job = AsyncMock(return_value={"uid": "job-uid"})
        # 첫 번째 폴링에서 즉시 에러 상태 반환
        mock_nexrender.get_job = AsyncMock(
            return_value={
                "state": "error",
                "error": "Rendering failed: Out of memory",
            }
        )

        with patch("worker.job_processor.NexrenderClient", return_value=mock_nexrender):
            processor = JobProcessor(test_config, mock_supabase_client)

            with pytest.raises(NexrenderError) as exc_info:
                await processor.process(sample_render_job)

            assert "렌더링 실패" in str(exc_info.value)

        # 에러 처리 호출 검증
        mock_supabase_client.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_validation_missing_file(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        mock_nexrender_client,
        sample_render_job: dict[str, Any],
    ):
        """파일 검증 - 파일 없음 테스트"""
        # 출력 파일을 생성하지 않음 (렌더링 실패 시뮬레이션)

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(test_config, mock_supabase_client)

            with pytest.raises(FileNotFoundError) as exc_info:
                await processor.process(sample_render_job)

            assert "출력 파일 없음" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_validation_empty_file(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        mock_nexrender_client,
        sample_render_job: dict[str, Any],
    ):
        """파일 검증 - 빈 파일 테스트"""
        # 빈 파일 생성
        output_path = Path(sample_render_job["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")  # 0 bytes

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(test_config, mock_supabase_client)

            with pytest.raises(ValueError) as exc_info:
                await processor.process(sample_render_job)

            assert "파일 크기 이상" in str(exc_info.value)

        output_path.unlink()

    @pytest.mark.asyncio
    async def test_nas_copy_success(
        self,
        mock_supabase_client,
        mock_nexrender_client,
        tmp_path: Path,
    ):
        """NAS 복사 성공 테스트"""
        # 임시 디렉토리 설정
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        nas_dir = tmp_path / "nas"
        nas_dir.mkdir()

        config = WorkerConfig(
            supabase_url="https://test.supabase.co",
            supabase_service_key="test_key",
            nexrender_url="http://localhost:3000",
            output_dir=str(output_dir),
            nas_output_path=str(nas_dir),
            render_timeout=60,
        )

        job = {
            "id": "nas-test-job",
            "aep_project": "/app/templates/test.aep",
            "aep_comp_name": "Main",
            "output_format": "mp4",
            "output_path": str(output_dir / "nas-test-job.mp4"),
            "gfx_data": {"slots": [], "single_fields": {}},
        }

        # 출력 파일 생성
        output_file = Path(job["output_path"])
        output_file.write_bytes(b"video content" * 1000)

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(config, mock_supabase_client)
            result = await processor.process(job)

        # NAS에 복사되었는지 확인
        nas_file = nas_dir / "nas-test-job.mp4"
        assert nas_file.exists()
        assert nas_file.stat().st_size > 0

        # 결과 경로가 NAS 경로인지 확인
        assert str(nas_dir) in result["output_path"]

    @pytest.mark.asyncio
    async def test_nas_copy_failure_graceful(
        self,
        mock_supabase_client,
        mock_nexrender_client,
        tmp_path: Path,
    ):
        """NAS 복사 실패 시 로컬 파일 유지 테스트"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = WorkerConfig(
            supabase_url="https://test.supabase.co",
            supabase_service_key="test_key",
            nexrender_url="http://localhost:3000",
            output_dir=str(output_dir),
            nas_output_path="//nonexistent/nas/path",  # 존재하지 않는 경로
            render_timeout=60,
        )

        job = {
            "id": "nas-fail-test",
            "aep_project": "/app/templates/test.aep",
            "aep_comp_name": "Main",
            "output_format": "mp4",
            "output_path": str(output_dir / "nas-fail-test.mp4"),
            "gfx_data": {"slots": [], "single_fields": {}},
        }

        # 출력 파일 생성
        output_file = Path(job["output_path"])
        output_file.write_bytes(b"video content" * 1000)

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(config, mock_supabase_client)
            result = await processor.process(job)

        # NAS 복사 실패해도 성공 반환 (로컬 파일 유지)
        assert result["status"] == "success"
        assert str(output_dir) in result["output_path"]
        assert output_file.exists()


class TestJobProcessorRetry:
    """재시도 로직 테스트"""

    @pytest.mark.asyncio
    async def test_retryable_error_increments_count(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        sample_render_job: dict[str, Any],
    ):
        """재시도 가능 에러 시 retry_count 증가 테스트"""
        # 네트워크 오류 시뮬레이션
        mock_nexrender = AsyncMock()
        mock_nexrender.submit_job = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch("worker.job_processor.NexrenderClient", return_value=mock_nexrender):
            processor = JobProcessor(test_config, mock_supabase_client)

            with pytest.raises(ConnectionError):
                await processor.process(sample_render_job)

        # mark_failed가 should_retry=True로 호출되었는지 확인
        call_args = mock_supabase_client.mark_failed.call_args
        assert call_args.kwargs.get("should_retry") is True

    @pytest.mark.asyncio
    async def test_non_retryable_error_marks_failed(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        sample_render_job: dict[str, Any],
    ):
        """재시도 불가 에러 시 즉시 실패 테스트"""
        # 잘못된 설정 오류 시뮬레이션 (재시도 불가)
        mock_nexrender = AsyncMock()
        mock_nexrender.submit_job = AsyncMock(
            side_effect=ValueError("Invalid configuration")
        )

        with patch("worker.job_processor.NexrenderClient", return_value=mock_nexrender):
            processor = JobProcessor(test_config, mock_supabase_client)

            with pytest.raises(ValueError):
                await processor.process(sample_render_job)

        # mark_failed가 should_retry=False로 호출되었는지 확인
        call_args = mock_supabase_client.mark_failed.call_args
        assert call_args.kwargs.get("should_retry") is False


class TestJobProcessorStatusTransitions:
    """상태 전환 테스트"""

    @pytest.mark.asyncio
    async def test_status_transitions_during_render(
        self,
        test_config: WorkerConfig,
        mock_supabase_client,
        mock_nexrender_client,
        sample_render_job: dict[str, Any],
    ):
        """렌더링 중 상태 전환 테스트"""
        # 출력 파일 생성
        output_path = Path(sample_render_job["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video" * 1000)

        with patch(
            "worker.job_processor.NexrenderClient", return_value=mock_nexrender_client
        ):
            processor = JobProcessor(test_config, mock_supabase_client)
            await processor.process(sample_render_job)

        # 상태 전환 호출 확인
        status_calls = [
            call[0][1] for call in mock_supabase_client.update_job_status.call_args_list
        ]

        # 예상 상태 전환: preparing -> rendering -> encoding -> uploading
        assert RenderStatus.PREPARING.value in status_calls
        assert RenderStatus.RENDERING.value in status_calls

        output_path.unlink()


class TestConfigValidation:
    """설정 검증 테스트"""

    def test_missing_required_env_vars(self):
        """필수 환경변수 누락 테스트"""
        from worker.config import ConfigurationError

        config = WorkerConfig()  # 빈 설정

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate(strict=True)

        assert "SUPABASE_URL" in str(exc_info.value)

    def test_invalid_url_format(self):
        """잘못된 URL 형식 테스트"""
        from worker.config import ConfigurationError

        config = WorkerConfig(
            supabase_url="not-a-valid-url",
            supabase_service_key="test_key",
        )

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate(strict=True)

        assert "잘못된 SUPABASE_URL 형식" in str(exc_info.value)

    def test_valid_config_passes_validation(self, tmp_path: Path):
        """유효한 설정 검증 통과 테스트"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = WorkerConfig(
            supabase_url="https://test.supabase.co",
            supabase_service_key="test_key",
            nexrender_url="http://localhost:3000",
            output_dir=str(output_dir),
            render_timeout=1800,
            max_retries=3,
        )

        # 예외 없이 통과해야 함
        warnings = config.validate(strict=True)
        assert isinstance(warnings, list)
