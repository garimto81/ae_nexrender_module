"""Basic test script for ultimate-debate skill.

This script validates core functionality without external dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from debate.consensus_checker import ConsensusChecker
from debate.context_manager import DebateContextManager
from debate.orchestrator import UltimateDebate


def test_consensus_checker():
    """Test consensus checking logic."""
    print("=== Testing ConsensusChecker ===")

    checker = ConsensusChecker(threshold=0.8)

    # Test 1: Full consensus
    analyses1 = [
        {"model": "claude", "conclusion": "Use GraphQL"},
        {"model": "gpt", "conclusion": "Use GraphQL"},
        {"model": "gemini", "conclusion": "Use GraphQL"},
    ]
    result1 = checker.check_consensus(analyses1)
    assert result1.status == "FULL_CONSENSUS", "Expected FULL_CONSENSUS"
    assert result1.consensus_percentage == 1.0, "Expected 100% consensus"
    print("[OK] Full consensus test passed")

    # Test 2: Partial consensus
    analyses2 = [
        {"model": "claude", "conclusion": "Use GraphQL"},
        {"model": "gpt", "conclusion": "Use GraphQL"},
        {"model": "gemini", "conclusion": "Use REST"},
    ]
    result2 = checker.check_consensus(analyses2)
    assert result2.status == "PARTIAL_CONSENSUS", "Expected PARTIAL_CONSENSUS"
    assert 0.5 <= result2.consensus_percentage < 0.8, "Expected 50-80% consensus"
    print("[OK] Partial consensus test passed")

    # Test 3: No consensus
    analyses3 = [
        {"model": "claude", "conclusion": "Use GraphQL"},
        {"model": "gpt", "conclusion": "Use REST"},
        {"model": "gemini", "conclusion": "Use gRPC"},
    ]
    result3 = checker.check_consensus(analyses3)
    assert result3.status == "NO_CONSENSUS", "Expected NO_CONSENSUS"
    assert result3.consensus_percentage < 0.5, "Expected <50% consensus"
    print("[OK] No consensus test passed")

    print()


def test_context_manager():
    """Test context manager file operations."""
    print("=== Testing DebateContextManager ===")

    import tempfile
    import shutil

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp())

    try:
        task_id = "test_debate_001"
        manager = DebateContextManager(task_id)

        # Override base path to temp directory
        manager.base_path = temp_dir / task_id
        manager.base_path.mkdir(parents=True, exist_ok=True)

        # Test save_task
        task_path = manager.save_task("Test task", {"created_at": "2026-01-18"})
        assert Path(task_path).exists(), "TASK.md should exist"
        print("[OK] save_task test passed")

        # Test save_round
        round_path = manager.save_round(
            0,
            "claude",
            {"analysis": "Test", "conclusion": "Test conclusion", "confidence": 0.9},
        )
        assert Path(round_path).exists(), "Round file should exist"
        print("[OK] save_round test passed")

        # Test save_consensus_result
        consensus_path = manager.save_consensus_result(
            0,
            {
                "status": "FULL_CONSENSUS",
                "agreed_items": [],
                "disputed_items": [],
                "consensus_percentage": 1.0,
                "next_action": None,
            },
        )
        assert Path(consensus_path).exists(), "CONSENSUS.md should exist"
        print("[OK] save_consensus_result test passed")

        # Test save_debate_round
        debate_path = manager.save_debate_round(
            0,
            "claude",
            {
                "updated_position": "Updated",
                "rebuttals": ["R1"],
                "concessions": ["C1"],
            },
        )
        assert Path(debate_path).exists(), "Debate file should exist"
        print("[OK] save_debate_round test passed")

        # Test generate_final_md
        final_path = manager.generate_final_md(
            {
                "status": "FULL_CONSENSUS",
                "final_strategy": {"conclusion": "Final"},
                "total_rounds": 1,
                "consensus_percentage": 1.0,
            }
        )
        assert Path(final_path).exists(), "FINAL.md should exist"
        print("[OK] generate_final_md test passed")

        # Test get_status
        status = manager.get_status()
        assert status["task_id"] == task_id, "Task ID should match"
        assert status["has_final"], "Should have FINAL.md"
        print("[OK] get_status test passed")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)

    print()


async def test_orchestrator():
    """Test debate orchestrator."""
    print("=== Testing UltimateDebate ===")

    debate = UltimateDebate(
        task="Test task",
        max_rounds=1,
        consensus_threshold=0.8,
    )

    # Test parallel analysis (with mock data)
    analyses = await debate.run_parallel_analysis()
    assert len(analyses) == 3, "Should have 3 analyses"
    print("[OK] run_parallel_analysis test passed")

    # Test consensus check
    debate.consensus_result = debate.consensus_checker.check_consensus(
        list(analyses.values())
    )
    assert debate.consensus_result is not None, "Should have consensus result"
    print("[OK] consensus check test passed")

    # Test debate round
    debates = await debate.run_debate_round()
    assert len(debates) == 3, "Should have 3 debate results"
    print("[OK] run_debate_round test passed")

    # Test final strategy
    final = debate.get_final_strategy()
    assert "status" in final, "Should have status"
    assert "final_strategy" in final, "Should have final_strategy"
    print("[OK] get_final_strategy test passed")

    # Test get_status
    status = debate.get_status()
    assert status["task_id"] == debate.task_id, "Task ID should match"
    print("[OK] get_status test passed")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Ultimate Debate Skill - Basic Tests")
    print("=" * 60 + "\n")

    try:
        test_consensus_checker()
        test_context_manager()
        asyncio.run(test_orchestrator())

        print("=" * 60)
        print("SUCCESS: All tests passed!")
        print("=" * 60 + "\n")

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"FAIL: Test failed: {e}")
        print("=" * 60 + "\n")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
