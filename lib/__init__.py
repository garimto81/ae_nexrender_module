"""
ae_nexrender_module 공통 라이브러리

Nexrender API 클라이언트, Job 빌더, 에러 처리, 경로 변환 유틸리티 제공.
"""

from .client import NexrenderClient, NexrenderSyncClient
from .errors import (
    NON_RETRYABLE_PATTERNS,
    RETRYABLE_PATTERNS,
    ErrorCategory,
    ErrorClassifier,
    NexrenderError,
)
from .job_builder import JobConfig, NexrenderJobBuilder
from .mapping_loader import MappingLoader, extract_template_name
from .path_utils import PathConverter, PathMapping
from .types import (
    ErrorCategory as ErrorCategoryEnum,
)
from .types import (
    JobConfig as JobConfigType,
)
from .types import (
    OutputFormat,
    RenderJob,
    RenderStatus,
    RenderType,
)

__all__ = [
    # Client
    "NexrenderClient",
    "NexrenderSyncClient",
    # Errors
    "ErrorCategory",
    "ErrorClassifier",
    "NexrenderError",
    "NON_RETRYABLE_PATTERNS",
    "RETRYABLE_PATTERNS",
    # Job Builder
    "JobConfig",
    "NexrenderJobBuilder",
    # Mapping Loader
    "MappingLoader",
    "extract_template_name",
    # Path Utils
    "PathConverter",
    "PathMapping",
    # Types
    "ErrorCategoryEnum",
    "JobConfigType",
    "OutputFormat",
    "RenderJob",
    "RenderStatus",
    "RenderType",
]
