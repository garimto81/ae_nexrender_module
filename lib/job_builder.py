"""
Nexrender Job JSON 빌더

두 가지 방식 지원:
1. GFX Data 기반 (gfx_json 방식) - 권장
2. Template 기반 (기존 automation_ae 방식) - 레거시 호환

레이어 매핑:
- GFX 필드명과 AEP 레이어명이 다를 경우 매핑 설정 파일 사용
- config/mappings/{template_name}.yaml 파일에서 매핑 정의
- 매핑이 없으면 GFX 필드명을 그대로 layerName으로 사용 (fallback)
"""

from dataclasses import dataclass
from typing import Any

from .mapping_loader import MappingLoader, extract_template_name
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

    레이어 매핑:
        GFX 필드명과 AEP 레이어명이 다를 경우 매핑 설정 파일을 통해 변환합니다.
        config/mappings/{template_name}.yaml 파일에서 컴포지션별 매핑을 정의합니다.
    """

    def __init__(self, config: JobConfig, mapping_loader: MappingLoader | None = None):
        """
        Args:
            config: Job 빌드 설정
            mapping_loader: 레이어 매핑 로더 (선택, 기본값: 자동 생성)
        """
        self.config = config
        self.path_converter = PathConverter()
        self.mapping_loader = mapping_loader or MappingLoader()
        self._template_name = extract_template_name(config.aep_project_path)

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
                assets.append(
                    {
                        "type": "data",
                        "layerName": layer_name,
                        "property": "Source Text",
                        "value": str(value),
                    }
                )
            elif layer_type == "image":
                assets.append(
                    {
                        "type": "image",
                        "layerName": layer_name,
                        "src": self.path_converter.to_file_url(str(value)),
                    }
                )
            elif layer_type == "video":
                assets.append(
                    {
                        "type": "video",
                        "layerName": layer_name,
                        "src": self.path_converter.to_file_url(str(value)),
                    }
                )

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
                "outputExt": "mp4",
                "outputModule": "Lossless with Alpha"  # mov_alpha인 경우
            }
        """
        template = {
            "src": self.path_converter.to_file_url(self.config.aep_project_path),
            "composition": self.config.composition_name,
            "continueOnMissing": True,
            "outputExt": self._get_output_extension(),
        }

        # 알파 채널 mov 출력 시 outputModule 지정
        output_module = self._get_output_module()
        if output_module:
            template["outputModule"] = output_module

        return template

    def _get_output_module(self) -> str | None:
        """출력 포맷에 따른 After Effects Output Module 반환

        mov_alpha: 알파 채널 출력
        - 한글 AE: "알파가 포함된 TIFF 시퀀스" 사용
        - 영문 AE: "TIFF Sequence with Alpha" 사용
        - 커스텀: 환경변수 NEXRENDER_OUTPUT_MODULE_ALPHA로 지정

        Returns:
            Output Module 이름 또는 None
        """
        import os

        if self.config.output_format.lower() == "mov_alpha":
            # 환경변수에서 커스텀 Output Module 이름 확인
            custom_module = os.getenv("NEXRENDER_OUTPUT_MODULE_ALPHA")
            if custom_module:
                return custom_module
            # 사용자 정의 Alpha MOV 템플릿 사용
            return "Alpha MOV"

        return None

    def _get_mapped_layer_name(self, gfx_field: str) -> str:
        """GFX 필드명을 AEP 레이어명으로 변환

        매핑 설정 파일에서 해당 컴포지션의 필드 매핑을 조회합니다.
        매핑이 없으면 원본 GFX 필드명을 그대로 반환합니다 (fallback).

        Args:
            gfx_field: GFX JSON 필드명 (예: "event_name", "slot1_name")

        Returns:
            AEP 레이어명 (매핑된 이름 또는 원본)
        """
        mapped_name = self.mapping_loader.get_layer_name(
            self._template_name,
            self.config.composition_name,
            gfx_field,
        )
        return mapped_name or gfx_field

    def _build_assets_from_gfx(self, gfx_data: dict[str, Any]) -> list[dict[str, Any]]:
        """gfx_data에서 assets 배열 생성

        GFX 데이터의 slots와 single_fields를 Nexrender assets 형식으로 변환합니다.
        레이어 매핑 설정이 있으면 GFX 필드명을 AEP 레이어명으로 변환합니다.

        Args:
            gfx_data: GFX 렌더링 데이터

        Returns:
            Nexrender assets 배열
        """
        assets = []

        # mov_alpha일 때 배경 레이어 비활성화 스크립트 추가
        if self.config.output_format.lower() == "mov_alpha":
            # 비활성화할 레이어 패턴 (배경, BG, background 등)
            disable_layers = gfx_data.get(
                "disable_layers",
                ["background", "Background", "BG", "bg", "배경", "solid", "Solid"],
            )
            disable_script = self._get_disable_layers_script(disable_layers)
            if disable_script:
                assets.append(disable_script)

        # Slots 처리 (슬롯 기반 반복 데이터)
        for slot in gfx_data.get("slots", []):
            slot_index = slot["slot_index"]
            for field_name, value in slot["fields"].items():
                gfx_field = f"slot{slot_index}_{field_name}"
                # 매핑된 레이어명 조회 (없으면 원본 사용)
                layer_name = self._get_mapped_layer_name(gfx_field)
                assets.append(
                    {
                        "type": "data",
                        "layerName": layer_name,
                        "property": "Source Text",
                        "value": str(value),
                    }
                )

        # Single Fields 처리 (단일 필드)
        for field_name, value in gfx_data.get("single_fields", {}).items():
            # 매핑된 레이어명 조회 (없으면 원본 사용)
            layer_name = self._get_mapped_layer_name(field_name)
            assets.append(
                {
                    "type": "data",
                    "layerName": layer_name,
                    "property": "Source Text",
                    "value": str(value),
                }
            )

        # Metadata에 직접 저장된 assets 병합 (이미지/비디오 등)
        if "assets" in gfx_data.get("metadata", {}):
            assets.extend(gfx_data["metadata"]["assets"])

        # 이미지 필드 처리 (테스트 호환)
        for image_info in gfx_data.get("images", []):
            assets.append(
                {
                    "type": "image",
                    "layerName": image_info.get("name", "image"),
                    "src": self.path_converter.to_file_url(image_info.get("path", "")),
                }
            )

        return assets

    def _get_disable_layers_script(
        self, layer_patterns: list[str]
    ) -> dict[str, Any] | None:
        """배경/비활성화할 레이어를 숨기는 JSX 스크립트 생성

        렌더링 전에 지정된 패턴과 일치하는 레이어들을 비활성화합니다.

        Args:
            layer_patterns: 비활성화할 레이어 이름 패턴 목록

        Returns:
            Nexrender script asset 또는 None
        """
        import base64

        patterns_js = ", ".join([f'"{p}"' for p in layer_patterns])

        jsx_script = f"""
// Disable Background Layers Script
// 배경 및 지정된 레이어를 비활성화

(function() {{
    var patterns = [{patterns_js}];
    var comp = app.project.activeItem;

    if (comp && comp instanceof CompItem) {{
        for (var i = 1; i <= comp.numLayers; i++) {{
            var layer = comp.layer(i);
            var layerName = layer.name.toLowerCase();

            // 패턴 매칭으로 레이어 비활성화
            for (var j = 0; j < patterns.length; j++) {{
                if (layerName.indexOf(patterns[j].toLowerCase()) !== -1) {{
                    layer.enabled = false;
                    $.writeln("Disabled layer: " + layer.name);
                    break;
                }}
            }}
        }}
    }}
}})();
"""
        encoded = base64.b64encode(jsx_script.encode("utf-8")).decode("utf-8")

        return {
            "type": "script",
            "src": f"data:text/javascript;base64,{encoded}",
        }

    def _get_alpha_output_script(self) -> dict[str, Any] | None:
        """알파 채널 mov 출력을 위한 JSX 스크립트 생성

        After Effects의 렌더 큐 Output Module을 동적으로 설정하여
        알파 채널이 포함된 QuickTime Animation 코덱으로 출력합니다.

        Returns:
            Nexrender script asset 또는 None
        """
        import base64

        # JSX 스크립트: Output Module을 QuickTime Animation + Alpha로 설정
        jsx_script = """
// Alpha MOV Output Configuration Script
// 렌더 큐의 Output Module을 알파 채널 포함 설정으로 변경

(function() {
    var rq = app.project.renderQueue;
    if (rq.numItems > 0) {
        var item = rq.item(rq.numItems);  // 마지막 렌더 큐 아이템
        var om = item.outputModule(1);

        // Output Module 설정 변경
        // QuickTime 포맷 + Animation 코덱 + RGB+Alpha
        try {
            // 사용 가능한 템플릿 확인 후 적용
            var templates = om.templates;
            var alphaTemplate = null;

            // 알파 채널 지원 템플릿 검색
            for (var i = 0; i < templates.length; i++) {
                var tpl = templates[i];
                if (tpl.indexOf("Alpha") !== -1 || tpl.indexOf("alpha") !== -1 ||
                    tpl.indexOf("4444") !== -1 || tpl.indexOf("Animation") !== -1) {
                    alphaTemplate = tpl;
                    break;
                }
            }

            if (alphaTemplate) {
                om.applyTemplate(alphaTemplate);
                $.writeln("Applied alpha template: " + alphaTemplate);
            } else {
                // 템플릿이 없으면 직접 설정 시도
                // Lossless 템플릿 적용 후 채널 설정 변경
                om.applyTemplate("Lossless");
                $.writeln("Applied Lossless template (alpha may not be included)");
            }
        } catch (e) {
            $.writeln("Error setting output module: " + e.toString());
        }
    }
})();
"""
        # Base64 인코딩하여 data URI로 변환
        encoded = base64.b64encode(jsx_script.encode("utf-8")).decode("utf-8")

        return {
            "type": "script",
            "src": f"data:text/javascript;base64,{encoded}",
        }

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
