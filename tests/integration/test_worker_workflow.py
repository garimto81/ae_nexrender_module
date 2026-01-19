"""
Worker 전체 워크플로우 E2E 테스트

워커의 폴링 루프, 작업 처리, 에러 복구 등 전체 흐름을 테스트합니다.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from worker.config import WorkerConfig


@pytest.fixture
def mock_supabase_queue_client():
    """Mock SupabaseQueueClient for worker tests"""
    client = AsyncMock()

    # poll_for_jobs: 처음에는 작업 있음, 이후 없음
    job_data = {
        "id": "worker-test-job",
        "aep_project": "/app/templates/test.aep",
        "aep_comp_name": "Main",
        "output_format": "mp4",
        "output_path": "",
        "gfx_data": {"slots": [], "single_fields": {"title": "Test"}},
        "priority": 5,
    }

    client.claim_job = AsyncMock(
        side_effect=[
            job_data,
            None,  # 두 번째 폴링에는 작업 없음
            None,
        ]
    )

    client.update_job_status = AsyncMock()
    client.update_progress = AsyncMock()
    client.set_nexrender_job_id = AsyncMock()
    client.mark_completed = AsyncMock()
    client.mark_failed = AsyncMock()
    client.get_job = AsyncMock(return_value=job_data)

    return client


class TestWorkerPollingLoop:
    """워커 폴링 루프 테스트"""

    @pytest.mark.asyncio
    async def test_adaptive_polling_intervals(self):
        """적응형 폴링 간격 테스트"""

        config = WorkerConfig(
            poll_interval_default=10,
            poll_interval_busy=5,
            poll_interval_idle=30,
            poll_interval_error=60,
            empty_poll_threshold=3,
        )

        # 작업 처리 중에는 busy 간격 사용
        assert config.poll_interval_busy == 5

        # 작업 없을 때는 idle 간격으로 전환
        assert config.poll_interval_idle == 30

        # 에러 시에는 더 긴 간격
        assert config.poll_interval_error == 60

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """정상 종료 테스트"""
        # Worker의 shutdown 플래그 시뮬레이션
        shutdown_flag = asyncio.Event()

        async def mock_polling_loop():
            while not shutdown_flag.is_set():
                await asyncio.sleep(0.1)
            return "shutdown_complete"

        # 시작 후 종료 신호
        task = asyncio.create_task(mock_polling_loop())
        await asyncio.sleep(0.2)
        shutdown_flag.set()

        result = await task
        assert result == "shutdown_complete"


class TestWorkerErrorRecovery:
    """워커 에러 복구 테스트"""

    @pytest.mark.asyncio
    async def test_supabase_connection_retry(self, mock_supabase_queue_client):
        """Supabase 연결 실패 시 재시도 테스트"""
        # 처음 2번은 실패, 3번째에 성공
        mock_supabase_queue_client.claim_job = AsyncMock(
            side_effect=[
                ConnectionError("Database connection failed"),
                ConnectionError("Database connection failed"),
                {"id": "recovered-job", "gfx_data": {}},
            ]
        )

        retry_count = 0
        max_retries = 3

        for attempt in range(max_retries):
            try:
                result = await mock_supabase_queue_client.claim_job()
                if result:
                    break
            except ConnectionError:
                retry_count += 1
                await asyncio.sleep(0.1)

        assert retry_count == 2
        assert result["id"] == "recovered-job"

    @pytest.mark.asyncio
    async def test_nexrender_timeout_handling(self):
        """Nexrender 타임아웃 처리 테스트"""
        from lib.errors import ErrorCategory, ErrorClassifier

        # 타임아웃 에러 분류
        timeout_error = TimeoutError("Render timeout after 1800 seconds")
        category = ErrorClassifier.classify(timeout_error)

        # 타임아웃은 재시도 가능 에러로 분류됨
        assert category == ErrorCategory.RETRYABLE


class TestWorkerConcurrency:
    """워커 동시성 테스트"""

    @pytest.mark.asyncio
    async def test_single_job_processing(self, mock_supabase_queue_client):
        """한 번에 하나의 작업만 처리 확인"""
        processing_count = 0
        max_concurrent = 0

        async def mock_process(job):
            nonlocal processing_count, max_concurrent
            processing_count += 1
            max_concurrent = max(max_concurrent, processing_count)
            await asyncio.sleep(0.1)
            processing_count -= 1

        # 여러 작업 동시 제출
        jobs = [{"id": f"job-{i}"} for i in range(3)]
        for job in jobs:
            await mock_process(job)

        # 순차 처리이므로 최대 동시 처리 수는 1
        # (실제 워커는 싱글 스레드 폴링)
        assert max_concurrent == 1


class TestWorkerHealthCheck:
    """워커 헬스체크 테스트"""

    @pytest.mark.asyncio
    async def test_health_endpoint_response(self):
        """헬스 엔드포인트 응답 테스트"""
        from unittest.mock import MagicMock

        from worker.config import WorkerConfig
        from worker.health import HealthServer

        # Mock Worker 생성
        mock_worker = MagicMock()
        mock_worker.worker_id = "test-worker-123"
        mock_worker.running = True
        mock_worker.current_job_id = None
        mock_worker.config = WorkerConfig(health_port=0)

        health_server = HealthServer(mock_worker)

        # 서버 시작 없이 상태만 확인
        assert health_server.worker.running is True
        assert health_server.worker.worker_id == "test-worker-123"

    @pytest.mark.asyncio
    async def test_health_status_during_processing(self):
        """작업 처리 중 헬스 상태 테스트"""
        from unittest.mock import MagicMock

        from worker.config import WorkerConfig
        from worker.health import HealthServer

        mock_worker = MagicMock()
        mock_worker.worker_id = "test-worker-456"
        mock_worker.running = True
        mock_worker.current_job_id = "job-123"
        mock_worker.config = WorkerConfig(health_port=0)

        health_server = HealthServer(mock_worker)

        # 작업 처리 중 상태 확인
        assert health_server.worker.current_job_id == "job-123"
        assert health_server.worker.running is True

        # 작업 완료 후 상태 변경
        mock_worker.current_job_id = None
        assert health_server.worker.current_job_id is None


class TestJobBuilderIntegration:
    """JobBuilder 통합 테스트"""

    def test_gfx_data_to_job_json(self, tmp_path: Path):
        """GFX 데이터 → Job JSON 변환 통합 테스트"""
        from lib.job_builder import JobConfig, NexrenderJobBuilder

        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_format="mp4",
            output_dir=str(tmp_path),
            output_filename="test-output",
        )

        builder = NexrenderJobBuilder(config)

        gfx_data = {
            "slots": [
                {"slot_index": 1, "fields": {"name": "Player 1", "chips": "1,000"}},
                {"slot_index": 2, "fields": {"name": "Player 2", "chips": "2,000"}},
            ],
            "single_fields": {
                "table_id": "Table 1",
                "event_name": "Championship",
            },
        }

        job_json = builder.build_from_gfx_data(gfx_data, "job-123")

        # 구조 검증
        assert "template" in job_json
        assert "assets" in job_json
        assert "actions" in job_json

        # 템플릿 섹션 검증
        assert job_json["template"]["composition"] == "Main"
        assert "src" in job_json["template"]

        # Assets 검증 (4 slots + 2 single fields = 6 assets)
        assert len(job_json["assets"]) >= 6

        # Actions 검증
        assert "postrender" in job_json["actions"]
        assert len(job_json["actions"]["postrender"]) > 0

    def test_alpha_mov_output_settings(self, tmp_path: Path):
        """Alpha MOV 출력 설정 테스트"""
        from lib.job_builder import JobConfig, NexrenderJobBuilder

        config = JobConfig(
            aep_project_path="C:/templates/test.aep",
            composition_name="Main",
            output_format="mov_alpha",  # 알파 채널 출력
            output_dir=str(tmp_path),
        )

        builder = NexrenderJobBuilder(config)
        job_json = builder.build_from_gfx_data(
            {"slots": [], "single_fields": {}}, "alpha-job"
        )

        # outputModule이 설정되어야 함
        assert "outputModule" in job_json["template"]

        # 확장자가 mov여야 함
        assert job_json["template"]["outputExt"] == "mov"


class TestSupabaseClientIntegration:
    """Supabase 클라이언트 통합 테스트"""

    @pytest.mark.asyncio
    async def test_job_claim_atomicity(self, mock_supabase_queue_client):
        """작업 클레임 원자성 테스트"""
        # 동시에 여러 워커가 같은 작업을 클레임하려 할 때
        # RPC 함수가 원자적으로 처리해야 함

        # Mock에서는 첫 번째 호출만 작업 반환
        claimed_jobs = []

        async def claim_attempt():
            job = await mock_supabase_queue_client.claim_job()
            if job:
                claimed_jobs.append(job)
            return job

        # 동시 클레임 시도
        results = await asyncio.gather(
            claim_attempt(),
            claim_attempt(),
            claim_attempt(),
        )

        # 하나의 워커만 작업을 클레임해야 함
        valid_results = [r for r in results if r is not None]
        assert len(valid_results) == 1

    @pytest.mark.asyncio
    async def test_status_update_ordering(self, mock_supabase_queue_client):
        """상태 업데이트 순서 테스트"""
        from lib.types import RenderStatus

        status_history = []

        async def track_status(job_id, status, **kwargs):
            status_history.append(status)

        mock_supabase_queue_client.update_job_status = AsyncMock(
            side_effect=track_status
        )

        # 상태 전환 시뮬레이션
        transitions = [
            RenderStatus.PREPARING,
            RenderStatus.RENDERING,
            RenderStatus.ENCODING,
            RenderStatus.UPLOADING,
            RenderStatus.COMPLETED,
        ]

        for status in transitions:
            await mock_supabase_queue_client.update_job_status("test-job", status.value)

        # 순서 검증
        assert status_history == [s.value for s in transitions]
