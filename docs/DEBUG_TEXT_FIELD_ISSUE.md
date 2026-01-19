# 텍스트 필드 렌더링 문제 분석 보고서

## 문제 요약
텍스트 필드 값(`event_name`, `tournament_name`, `table_id`)이 렌더링 결과에 적용되지 않음

## 근본 원인

### After Effects 레이어 이름 불일치

Nexrender Job JSON에서 생성하는 `layerName`과 실제 AE 프로젝트의 텍스트 레이어 이름이 일치하지 않음.

**생성된 Job JSON:**
```json
{
  "assets": [
    {
      "type": "data",
      "layerName": "event_name",
      "property": "Source Text",
      "value": "TEXT CHANGE TEST 2026"
    }
  ]
}
```

**실제 AE 레이어 이름:**
- `"EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE"` (텍스트 내용 그대로)

Nexrender는 `layerName`으로 레이어를 검색하므로, `"event_name"` 레이어를 찾을 수 없어 텍스트가 적용되지 않음.

## 컴포지션 레이어 분석

### 1-Hand-for-hand play is currently in progress

```json
{
  "layers": [
    {
      "name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
      "layerClass": "TextLayer",
      "textContent": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE"
    },
    {
      "name": "NEXT STREAM STARTING SOON",
      "layerClass": "TextLayer",
      "textContent": "NEXT STREAM STARTING SOON",
      "enabled": false
    }
  ]
}
```

**문제점:**
- 레이어 이름이 실제 텍스트 내용과 동일 (표준화되지 않음)
- `event_name`, `tournament_name` 등의 필드명으로 매핑 불가

## 해결 방안

### 방안 1: AE 프로젝트 레이어 이름 변경 (권장)

After Effects에서 텍스트 레이어 이름을 표준화:

| 현재 레이어 이름 | 변경할 이름 | 용도 |
|-----------------|------------|------|
| `EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE` | `event_name` | 이벤트명 |
| `NEXT STREAM STARTING SOON` | `tournament_name` | 토너먼트명 |
| (찾을 수 없음) | `table_id` | 테이블 ID |
| (찾을 수 없음) | `message` | 메시지 |

**장점:**
- 코드 수정 불필요
- 다른 컴포지션도 동일 패턴 적용 가능
- 명확한 의미 전달

**작업:**
1. CyprusDesign.aep 열기
2. 각 컴포지션의 텍스트 레이어 이름 변경
3. 프로젝트 저장
4. `CyprusDesign_analysis.json` 재생성 (선택)

### 방안 2: 레이어 이름 매핑 추가 (임시)

`sample_data.py`에 컴포지션별 레이어 이름 매핑 추가:

```python
LAYER_NAME_MAPPING = {
    "1-Hand-for-hand play is currently in progress": {
        "event_name": "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE",
        "tournament_name": "NEXT STREAM STARTING SOON",
        # table_id, message는 레이어 없음 (추가 필요)
    }
}
```

`job_builder.py`에서 매핑 적용:

```python
def _build_assets_from_gfx(self, gfx_data: dict[str, Any]) -> list[dict[str, Any]]:
    assets = []

    # 레이어 이름 매핑 조회
    mapping = LAYER_NAME_MAPPING.get(self.config.composition_name, {})

    for field_name, value in gfx_data.get("single_fields", {}).items():
        # 매핑된 실제 레이어 이름 사용
        layer_name = mapping.get(field_name, field_name)

        assets.append({
            "type": "data",
            "layerName": layer_name,
            "property": "Source Text",
            "value": str(value),
        })

    return assets
```

**단점:**
- 모든 컴포지션마다 매핑 필요
- 유지보수 복잡
- 레이어가 없으면 여전히 실패

## 추가 조사 필요

### 누락된 텍스트 레이어

다음 필드에 해당하는 텍스트 레이어를 찾을 수 없음:

- `table_id`: "Table 1" 표시용 레이어
- `message`: "Hand-for-hand play is currently in progress" 메시지 레이어

**가능성:**
1. 레이어가 다른 이름으로 존재 (Shape Layer에 포함?)
2. 실제로 레이어가 없음 (추가 필요)
3. 다른 컴포지션에 존재 (`2-Hand-for-hand...`)

## 권장 조치

### 즉시 조치 (방안 1 선택)

1. After Effects에서 `CyprusDesign.aep` 열기
2. 다음 컴포지션들의 텍스트 레이어 이름 변경:
   - `1-Hand-for-hand play is currently in progress`
   - `1-NEXT STREAM STARTING SOON`
   - `2-Hand-for-hand play is currently in progress`
   - `2-NEXT STREAM STARTING SOON`
   - `4-NEXT STREAM STARTING SOON`

3. 표준 레이어 이름 규칙:
   ```
   event_name          - 이벤트명
   tournament_name     - 토너먼트명
   table_id            - 테이블 ID
   message             - 메시지
   next_stream_time    - 다음 스트림 시간
   ```

4. 슬롯 기반 컴포지션 (`2-`, `4-`):
   ```
   slot1_table_id      - 슬롯1 테이블 ID
   slot2_table_id      - 슬롯2 테이블 ID
   slot1_tournament_name - 슬롯1 토너먼트명
   ...
   ```

5. 저장 후 테스트:
   ```powershell
   python scripts/test_render.py --composition "1-Hand-for-hand play is currently in progress" \
     --field event_name="TEXT CHANGE TEST 2026" \
     --field tournament_name="VERIFICATION RENDER" \
     --field table_id="TABLE-999" \
     --dry-run
   ```

### 장기 조치

1. **템플릿 표준 문서 작성**
   - 모든 AE 템플릿의 레이어 이름 규칙 문서화
   - `docs/AE_TEMPLATE_STANDARD.md`

2. **자동 검증 스크립트**
   - AE 프로젝트 분석 시 레이어 이름 규칙 검증
   - 불일치 경고 출력

3. **단위 테스트 추가**
   - 실제 AE 프로젝트와 `sample_data.py` 일치 검증
   - CI에서 자동 실행

## 참고 자료

- Nexrender 공식 문서: https://github.com/inlife/nexrender
- Assets 타입: `data`, `image`, `video`, `audio`, `script`
- `layerName` 매칭: 정확한 문자열 일치 필요 (대소문자 구분)

## 테스트 결과

### 생성된 Job JSON (현재)

```json
{
  "template": {
    "src": "file:///C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep",
    "composition": "1-Hand-for-hand play is currently in progress"
  },
  "assets": [
    {
      "type": "data",
      "layerName": "event_name",
      "property": "Source Text",
      "value": "TEXT CHANGE TEST 2026"
    },
    {
      "layerName": "tournament_name",
      "value": "VERIFICATION RENDER"
    },
    {
      "layerName": "table_id",
      "value": "TABLE-999"
    }
  ]
}
```

### 실제 AE 레이어 구조

```
Composition: 1-Hand-for-hand play is currently in progress
├── TextLayer: "EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE" (enabled)
├── TextLayer: "NEXT STREAM STARTING SOON" (disabled)
├── ShapeLayer: "Shape Layer 31" (disabled)
├── ShapeLayer: "Shape Layer 29" (disabled)
├── ShapeLayer: "Shape Layer 8" (enabled)
├── ShapeLayer: "Shape Layer 23" (enabled)
├── ShapeLayer: "Shape Layer 30" (disabled)
├── AVLayer: "shutterstock_3778623699.mp4" (video, x2)
└── AVLayer: "BG작업_W.jpg" (background)
```

### 불일치 항목

| 코드 layerName | 실제 레이어 이름 | 상태 |
|---------------|----------------|------|
| `event_name` | `EVENT #12: $5,000 MEGA MYSTERY BOUNTY RAFFLE` | 불일치 |
| `tournament_name` | `NEXT STREAM STARTING SOON` (disabled) | 불일치 + 비활성화 |
| `table_id` | (없음) | 누락 |
| `message` | (없음) | 누락 |

---

**작성일**: 2026-01-16
**작성자**: Claude Code
**프로젝트**: ae_nexrender_module
