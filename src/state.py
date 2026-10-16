from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class PipelineStage(str, Enum):
    INIT = "INIT"
    PARSING = "PARSING"
    PBT = "PBT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    FAILED = "FAILED"
    PASSED = "PASSED"

class PipelineState(TypedDict, total=False):
    file_path: str
    stage: PipelineStage
    extracted_functions: List[Dict[str, Any]]
    pbt_results: List[Any]
    verification_status: VerificationStatus
    error: Optional[str]
