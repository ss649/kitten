from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class PipelineStage(str, Enum):
    INIT = "INIT"
    PARSING = "PARSING"
    PBT = "PBT"
    SOUNDNESS_GATE = "SOUNDNESS_GATE"
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
    generated_properties: List[Dict[str, Any]]
    verified_properties: List[Dict[str, Any]]
    refuted_properties: List[Dict[str, Any]]
    undecided_properties: List[Dict[str, Any]]
    pbt_results: List[Any]
    verification_status: VerificationStatus
    error: Optional[str]
