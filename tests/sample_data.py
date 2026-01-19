"""
테스트용 샘플 GFX 데이터 생성기

CyprusDesign.aep 템플릿의 실제 컴포지션과 텍스트 레이어를 기반으로
테스트용 샘플 데이터를 생성합니다.
"""

import random
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# 실제 CyprusDesign.aep 컴포지션 목록 (일부)
SAMPLE_COMPOSITIONS = [
    "1-Hand-for-hand play is currently in progress",
    "1-NEXT STREAM STARTING SOON",
    "2-Hand-for-hand play is currently in progress",
    "2-NEXT STREAM STARTING SOON",
    "4-NEXT STREAM STARTING SOON",
]

# 컴포지션별 텍스트 레이어 매핑
COMPOSITION_LAYERS = {
    "1-Hand-for-hand play is currently in progress": {
        "single_fields": {
            "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
            "message": "Hand-for-hand play is currently in progress",
            "table_id": "Table 1",
        },
        "slots": [],
    },
    "1-NEXT STREAM STARTING SOON": {
        "single_fields": {
            "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
            "next_stream_time": "Starting in 15 minutes",
            "tournament_name": "WSOP MAIN EVENT",
        },
        "slots": [],
    },
    "2-Hand-for-hand play is currently in progress": {
        "single_fields": {
            "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
            "message": "Hand-for-hand play is currently in progress",
        },
        "slots": [
            {"slot_index": 1, "field_names": ["table_id"]},
            {"slot_index": 2, "field_names": ["table_id"]},
        ],
    },
    "2-NEXT STREAM STARTING SOON": {
        "single_fields": {
            "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
            "next_stream_time": "Starting in 15 minutes",
        },
        "slots": [
            {"slot_index": 1, "field_names": ["tournament_name"]},
            {"slot_index": 2, "field_names": ["tournament_name"]},
        ],
    },
    "4-NEXT STREAM STARTING SOON": {
        "single_fields": {
            "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
        },
        "slots": [
            {"slot_index": 1, "field_names": ["tournament_name", "next_stream_time"]},
            {"slot_index": 2, "field_names": ["tournament_name", "next_stream_time"]},
            {"slot_index": 3, "field_names": ["tournament_name", "next_stream_time"]},
            {"slot_index": 4, "field_names": ["tournament_name", "next_stream_time"]},
        ],
    },
    # 테스트용 별칭 (conftest.py에서 사용 - 테스트 기대값에 맞춤)
    "basic": {
        "single_fields": {
            "table_id": "Table 1",
            "tournament": "WSOP 2024",
        },
        "slots": [
            {"slot_index": 1, "field_names": ["name", "chips"]},
        ],
        # 테스트용 고정값
        "_fixed_values": {
            "slot1_name": "PHIL IVEY",
            "slot1_chips": "1,234,567",
        },
    },
    "multi_slot": {
        "single_fields": {},
        "slots": [
            {"slot_index": i, "field_names": ["name", "chips"]}
            for i in range(1, 9)  # 8 slots
        ],
        # 테스트용 고정값
        "_fixed_values": {f"slot{i}_name": f"Player {i}" for i in range(1, 9)},
    },
    "with_images": {
        "single_fields": {},
        "slots": [],
        "images": [
            {"name": "background_image", "path": "C:/images/background.png"},
        ],
    },
}

# 샘플 데이터 풀
SAMPLE_EVENT_NAMES = [
    "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
    "EVENT #15: $10,000 NO-LIMIT HOLD'EM",
    "EVENT #20: $1,500 POT-LIMIT OMAHA",
    "MAIN EVENT: $10,000 NO-LIMIT HOLD'EM CHAMPIONSHIP",
]

SAMPLE_TOURNAMENT_NAMES = [
    "WSOP MAIN EVENT",
    "WSOP BRACELET RACE",
    "WSOP HIGH ROLLER",
    "WSOP SUPER CIRCUIT",
]

SAMPLE_TABLE_IDS = ["Table 1", "Table 2", "Table 3", "Table 4"]

SAMPLE_MESSAGES = [
    "Hand-for-hand play is currently in progress",
    "Final table in progress",
    "Tournament starting soon",
    "Break time - 15 minutes",
]


def generate_sample_gfx_data(composition_name: str) -> dict[str, Any]:
    """컴포지션에 맞는 샘플 GFX 데이터 생성

    Args:
        composition_name: 컴포지션 이름

    Returns:
        GFX 데이터 딕셔너리
            {
                "slots": [
                    {
                        "slot_index": 1,
                        "fields": {"tournament_name": "WSOP MAIN EVENT"}
                    }
                ],
                "single_fields": {
                    "event_name": "EVENT #12: ...",
                    "message": "Hand-for-hand..."
                },
                "images": [
                    {"name": "background_image", "path": "C:/images/bg.png"}
                ]
            }
    """
    if composition_name not in COMPOSITION_LAYERS:
        raise ValueError(f"Unknown composition: {composition_name}")

    template = COMPOSITION_LAYERS[composition_name]
    gfx_data: dict[str, Any] = {"slots": [], "single_fields": {}}

    # 테스트용 고정값 조회
    fixed_values = template.get("_fixed_values", {})

    # Single fields 생성
    for field_name in template["single_fields"]:
        if field_name == "event_name":
            value = random.choice(SAMPLE_EVENT_NAMES)
        elif field_name == "tournament_name":
            value = random.choice(SAMPLE_TOURNAMENT_NAMES)
        elif field_name == "table_id":
            value = template["single_fields"].get(
                "table_id", random.choice(SAMPLE_TABLE_IDS)
            )
        elif field_name == "tournament":
            value = template["single_fields"].get("tournament", "WSOP 2024")
        elif field_name == "message":
            value = random.choice(SAMPLE_MESSAGES)
        elif field_name == "next_stream_time":
            value = f"Starting in {random.randint(5, 30)} minutes"
        else:
            value = template["single_fields"][field_name]

        gfx_data["single_fields"][field_name] = value

    # Slots 생성
    for slot_template in template["slots"]:
        slot_index = slot_template["slot_index"]
        fields = {}

        for field_name in slot_template["field_names"]:
            # 고정값 키 생성 (slot1_name, slot1_chips 등)
            fixed_key = f"slot{slot_index}_{field_name}"

            if fixed_key in fixed_values:
                value = fixed_values[fixed_key]
            elif field_name == "tournament_name":
                value = random.choice(SAMPLE_TOURNAMENT_NAMES)
            elif field_name == "table_id":
                value = random.choice(SAMPLE_TABLE_IDS)
            elif field_name == "next_stream_time":
                value = f"Starting in {random.randint(5, 30)} minutes"
            else:
                value = f"Slot {slot_index} {field_name}"

            fields[field_name] = value

        gfx_data["slots"].append({"slot_index": slot_index, "fields": fields})

    # 이미지 추가 (테스트용)
    if "images" in template:
        gfx_data["images"] = template["images"]

    return gfx_data


def generate_sample_render_request(
    composition_name: str | None = None,
    output_format: str = "mp4",
    priority: int = 5,
) -> dict[str, Any]:
    """render_queue INSERT용 샘플 데이터 생성

    Args:
        composition_name: 컴포지션 이름 (None이면 랜덤 선택)
        output_format: 출력 포맷 (mp4, mov, mov_alpha, png_sequence)
        priority: 우선순위 (1-10)

    Returns:
        render_queue INSERT용 딕셔너리
            {
                "id": "uuid",
                "composition_name": "...",
                "aep_project_path": "...",
                "gfx_data": {...},
                "output_format": "mp4",
                "priority": 5,
                ...
            }
    """
    # 컴포지션 선택
    comp_name = composition_name or random.choice(SAMPLE_COMPOSITIONS)

    # GFX 데이터 생성
    gfx_data = generate_sample_gfx_data(comp_name)

    # 작업 ID 생성
    job_id = str(uuid4())

    # AEP 프로젝트 경로 (실제 CyprusDesign.aep 경로)
    aep_project_path = "C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep"

    return {
        "id": job_id,
        "composition_name": comp_name,
        "aep_project_path": aep_project_path,
        "gfx_data": gfx_data,
        "output_format": output_format,
        "output_filename": f"test_render_{job_id[:8]}",
        "priority": priority,
        "status": "pending",
        "progress": 0,
        "max_retries": 3,
        "retry_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_batch_render_requests(count: int = 5) -> list[dict[str, Any]]:
    """여러 개의 샘플 렌더링 요청 생성

    Args:
        count: 생성할 작업 개수

    Returns:
        렌더링 요청 리스트
    """
    requests = []

    for i in range(count):
        # 다양한 조합 생성
        comp_name = SAMPLE_COMPOSITIONS[i % len(SAMPLE_COMPOSITIONS)]
        output_format = ["mp4", "mov"][i % 2]
        priority = (i % 10) + 1

        request = generate_sample_render_request(
            composition_name=comp_name,
            output_format=output_format,
            priority=priority,
        )
        requests.append(request)

    return requests


def generate_sample_template() -> dict[str, Any]:
    """레거시 템플릿 데이터 생성 (JobBuilder 테스트용)

    Returns:
        템플릿 데이터 딕셔너리
    """
    return {
        "file_path": "/app/templates/test.aep",
        "composition": "Main",
        "output_dir": "/app/output",
        "output_filename": "test_output",
        "output_format": "mp4",
        # 레이어는 dict 형식 (layerName: {type: ...})
        "layers": {
            "player1_name": {"type": "text"},
            "player1_chips": {"type": "text"},
            "background_image": {"type": "image"},
            "logo": {"type": "image"},
        },
    }


def generate_sample_layer_data() -> dict[str, Any]:
    """레거시 레이어 데이터 생성 (JobBuilder 테스트용)

    Returns:
        레이어 데이터 딕셔너리
    """
    return {
        "player1_name": "PHIL IVEY",
        "player1_chips": "1,234,567",
        "background_image": "/path/to/background.png",
        "logo": "/path/to/logo.png",
    }


# 사용 예시
if __name__ == "__main__":
    # 단일 작업 생성
    single_request = generate_sample_render_request()
    print("=== 단일 작업 예시 ===")
    print(f"Composition: {single_request['composition_name']}")
    print(f"GFX Data: {single_request['gfx_data']}")

    # 배치 작업 생성
    batch_requests = generate_batch_render_requests(count=3)
    print("\n=== 배치 작업 예시 (3개) ===")
    for i, req in enumerate(batch_requests, 1):
        print(f"\n작업 {i}:")
        print(f"  Composition: {req['composition_name']}")
        print(f"  Output: {req['output_format']}")
        print(f"  Priority: {req['priority']}")
