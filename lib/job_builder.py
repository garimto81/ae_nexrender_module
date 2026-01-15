"""
Nexrender Job JSON 빌더

두 가지 방식 지원:
1. GFX Data 기반 (gfx_json 방식) - 권장
2. Template 기반 (기존 automation_ae 방식) - 레거시 호환
"""

from dataclasses import dataclass
from typing import Any

from .path_utils import PathConverter


@dataclass
class JobConfig:
    """Job 빌드 설정"""
    aep_project_path: str
    composition_name: str
    output_format: str = "mp4"
    output_dir: str = ""
    output_filename: str = ""
    callback_url: str | None = None


class NexrenderJobBuilder:
    """Nexrender Job JSON 빌더

    GFX Data 또는 Template 기반으로 Nexrender가 이해하는 Job JSON을 생성합니다.
    """

    def __init__(self, config: JobConfig):
        """
        Args:
            config: Job 빌드 설정
        """
        self.config = config
        self.path_converter = PathConverter()

    def build_from_gfx_data(
        self,
        gfx_data: dict[str, Any],
        job_id: str,
    ) -> dict[str, Any]:
        """gfx_data에서 Nexrender Job JSON 생성

        GFX 렌더링 시스템에서 생성된 gfx_data를 Nexrender Job으로 변환합니다.

        Args:
            gfx_data: GFX 렌더링 데이터 (slots, single_fields 포함)
                {
                    "comp_name": "Main",
                    "slots": [{"slot_index": 1, "fields": {"name": "PHIL IVEY"}}],
                    "single_fields": {"table_id": "Table 1"}
                }
            job_id: 작업 ID (출력 파일명에 사용)

        Returns:
            Nexrender Job JSON
                {
                    "template": {...},
                    "assets": [...],
                    "actions": {...}
                }
        """
        job_data = {
            "template": self._build_template_section(),
            "assets": self._build_assets_from_gfx(gfx_data),
            "actions": self._build_actions_section(job_id),
        }

        # 콜백 URL 추가 (Webhook 모드)
        if self.config.callback_url:
            job_data["callback"] = f"{self.config.callback_url}/{job_id}"

        return job_data

    def build_from_template(
        self,
        template: dict[str, Any],
        data: dict[str, Any],
        job_id: int,
    ) -> dict[str, Any]:
        """Template 모델에서 Nexrender Job JSON 생성 (레거시 호환)

        기존 automation_ae의 Template 기반 방식과 호환됩니다.

        Args:
            template: 템플릿 정보
                {
                    "file_path": "/app/templates/file.aep",
                    "composition": "Main",
                    "layers": {
                        "text_layer_1": {"type": "text"},
                        "image_layer_1": {"type": "image"}
                    }
                }
            data: 레이어 데이터
                {
                    "text_layer_1": "Hello World",
                    "image_layer_1": "/path/to/image.png"
                }
            job_id: 작업 ID

        Returns:
            Nexrender Job JSON
        """
        # Template 데이터 기반 assets 생성
        assets = []
        layers = template.get("layers", {})

        for layer_name, layer_info in layers.items():
            if layer_name not in data:
                continue

            value = data[layer_name]
            layer_type = layer_info.get("type", "text")

            if layer_type == "text":
                assets.append({
                    "type": "data",
                    "layerName": layer_name,
                    "property": "Source Text",
                    "value": str(value),
                })
            elif layer_type == "image":
                assets.append({
                    "type": "image",
                    "layerName": layer_name,
                    "src": self.path_converter.to_file_url(str(value)),
                })
            elif layer_type == "video":
                assets.append({
                    "type": "video",
                    "layerName": layer_name,
                    "src": self.path_converter.to_file_url(str(value)),
                })

        return {
            "template": self._build_template_section(),
            "assets": assets,
            "actions": self._build_actions_section(str(job_id)),
        }

    def _build_template_section(self) -> dict[str, Any]:
        """template 섹션 생성

        Returns:
            {
                "src": "file:///C:/path/to/template.aep",
                "composition": "Main",
                "outputExt": "mp4"
            }
        """
        return {
            "src": self.path_converter.to_file_url(self.config.aep_project_path),
            "composition": self.config.composition_name,
            "continueOnMissing": True,
            "outputExt": self._get_output_extension(),
        }

    def _build_assets_from_gfx(self, gfx_data: dict[str, Any]) -> list[dict[str, Any]]:
        """gfx_data에서 assets 배열 생성

        GFX 데이터의 slots와 single_fields를 Nexrender assets 형식으로 변환합니다.

        Args:
            gfx_data: GFX 렌더링 데이터

        Returns:
            Nexrender assets 배열
        """
        assets = []

        # Slots 처리 (슬롯 기반 반복 데이터)
        for slot in gfx_data.get("slots", []):
            slot_index = slot["slot_index"]
            for field_name, value in slot["fields"].items():
                layer_name = f"slot{slot_index}_{field_name}"
                assets.append({
                    "type": "data",
                    "layerName": layer_name,
                    "property": "Source Text",
                    "value": str(value),
                })

        # Single Fields 처리 (단일 필드)
        for field_name, value in gfx_data.get("single_fields", {}).items():
            assets.append({
                "type": "data",
                "layerName": field_name,
                "property": "Source Text",
                "value": str(value),
            })

        # Metadata에 직접 저장된 assets 병합 (이미지/비디오 등)
        if "assets" in gfx_data.get("metadata", {}):
            assets.extend(gfx_data["metadata"]["assets"])

        # 이미지 필드 처리 (테스트 호환)
        for image_info in gfx_data.get("images", []):
            assets.append({
                "type": "image",
                "layerName": image_info.get("name", "image"),
                "src": self.path_converter.to_file_url(image_info.get("path", "")),
            })

        return assets

    def _build_actions_section(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        """actions 섹션 생성 (후처리)

        렌더링 완료 후 파일을 지정된 경로로 복사합니다.

        Args:
            job_id: 작업 ID

        Returns:
            {
                "postrender": [
                    {
                        "module": "@nexrender/action-copy",
                        "input": "result.mp4",
                        "output": "C:/output/job_123.mp4"
                    }
                ]
            }
        """
        # 출력 파일명 결정
        output_filename = self.config.output_filename or job_id
        if "." in output_filename:
            # 확장자 제거 (자동으로 추가됨)
            output_filename = output_filename.rsplit(".", 1)[0]

        # 출력 경로 구성
        output_ext = self._get_output_extension()
        output_path = self.path_converter.to_windows_path(
            f"{self.config.output_dir}/{output_filename}.{output_ext}"
        )

        return {
            "postrender": [
                {
                    "module": "@nexrender/action-copy",
                    "input": f"result.{output_ext}",
                    "output": output_path,
                }
            ]
        }

    def _get_output_extension(self) -> str:
        """출력 포맷에 따른 확장자

        Returns:
            파일 확장자 (mp4, mov, png 등)
        """
        format_map = {
            "mp4": "mp4",
            "mov": "mov",
            "mov_alpha": "mov",
            "png_sequence": "png",
        }
        return format_map.get(self.config.output_format.lower(), "mp4")
