"""
ae_nexrender_module 공통 라이브러리

Nexrender API 클라이언트, Job 빌더, 에러 처리, 경로 변환 유틸리티 제공.
"""

from .client import NexrenderClient, NexrenderSyncClient
from .errors import (
    ErrorCategory,
    ErrorClassifier,
    NexrenderError,
    NON_RETRYABLE_PATTERNS,
    RETRYABLE_PATTERNS,
)
from .job_builder import JobConfig, NexrenderJobBuilder
from .path_utils import PathConverter, PathMapping
from .types import (
    ErrorCategory as ErrorCategoryEnum,
    JobConfig as JobConfigType,
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
