"""Ultimate Debate 통합 테스트

auto-workflow와 ultimate-debate 통합 검증
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import sys

# 모듈 경로 추가
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from auto_discovery import AutoDiscovery, Priority, CONTEXT_ESTIMATES


class TestDebatePriorityLevel:
    """Tier 3.5 우선순위 테스트"""

    def test_debate_priority_between_tier3_and_tier4(self):
        """DEBATE_ANALYSIS는 Tier 3과 Tier 4 사이"""
        assert Priority.RESEARCH_REVIEW < Priority.DEBATE_ANALYSIS
        assert Priority.DEBATE_ANALYSIS < Priority.CODE_QUALITY


class TestDebateContextEstimates:
    """Debate Context 예산 테스트"""

    def test_debate_small_estimate(self):
        """debate_small 예산: 20%"""
        assert CONTEXT_ESTIMATES["debate_small"] == 20

    def test_debate_medium_estimate(self):
        """debate_medium 예산: 35%"""
        assert CONTEXT_ESTIMATES["debate_medium"] == 35

    def test_debate_large_estimate(self):
        """debate_large 예산: 50%"""
        assert CONTEXT_ESTIMATES["debate_large"] == 50


class TestDebateDetection:
    """Debate 감지 로직 테스트"""

    def test_detect_decision_required_marker(self):
        """PRD에서 DECISION_REQUIRED 마커 감지"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # PRD 디렉토리 생성
            prd_dir = Path(tmpdir) / "tasks" / "prds"
            prd_dir.mkdir(parents=True)

            # DECISION_REQUIRED 마커가 있는 PRD 생성
            prd_file = prd_dir / "test-prd.md"
            prd_file.write_text("""# Test PRD

<!-- DECISION_REQUIRED -->
캐싱 전략 선택: Redis vs Memcached

## Options
- Option A: Redis
- Option B: Memcached
""")

            discovery = AutoDiscovery(project_root=tmpdir)
            task = discovery._check_prd_decision_required()

            assert task is not None
            assert task.priority == Priority.DEBATE_ANALYSIS
            assert "DECISION_REQUIRED" in task.details.get("trigger", "")

    def test_detect_architecture_options(self):
        """아키텍처 문서에서 Option 패턴 감지"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # docs 디렉토리 생성
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir(parents=True)

            # Option 패턴이 있는 문서 생성
            arch_file = docs_dir / "architecture.md"
            arch_file.write_text("""# Architecture Decision

## Database Selection

Option A: PostgreSQL
- 장점: ACID 완전 지원
- 단점: 샤딩 복잡

Option B: MongoDB
- 장점: 유연한 스키마
- 단점: 트랜잭션 제한

Option C: DynamoDB
- 장점: 관리형 서비스
- 단점: 벤더 락인
""")

            discovery = AutoDiscovery(project_root=tmpdir)
            task = discovery._check_architecture_options()

            assert task is not None
            assert task.priority == Priority.DEBATE_ANALYSIS
            assert "ARCHITECTURE_OPTIONS" in task.details.get("trigger", "")

    def test_no_detection_when_selected(self):
        """선택됨 표시가 있으면 감지하지 않음"""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir(parents=True)

            arch_file = docs_dir / "architecture.md"
            arch_file.write_text("""# Architecture Decision

## Database Selection

Option A: PostgreSQL (selected)
Option B: MongoDB
""")

            discovery = AutoDiscovery(project_root=tmpdir)
            task = discovery._check_architecture_options()

            assert task is None


class TestContextPredictorDebate:
    """Context Predictor debate 테스트"""

    def test_debate_estimates_in_context_predictor(self):
        """context_predictor에 debate 예산 포함"""
        from context_predictor import TASK_CONTEXT_ESTIMATES

        assert "debate_small" in TASK_CONTEXT_ESTIMATES
        assert "debate_medium" in TASK_CONTEXT_ESTIMATES
        assert "debate_large" in TASK_CONTEXT_ESTIMATES


class TestStatusReport:
    """상태 리포트 테스트"""

    def test_status_report_includes_tier3_5(self):
        """상태 리포트에 tier3_5_debate 포함"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = AutoDiscovery(project_root=tmpdir)
            report = discovery.get_status_report()

            assert "tier3_5_debate" in report
            assert "debate_needed" in report["tier3_5_debate"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
