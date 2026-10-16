from __future__ import annotations

from enum import Enum
import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

#Sample pipeline design
class PipelineStage(str, Enum): 
    INIT = "INIT"
    PARSING = "PARSING"
    INITIAL_PBT = "INITIAL_PBT"
    LEAN_KERNEL_CHECK = "LEAN_KERNEL_CHECK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    PBT_REJECTED = "PBT_REJECTED"
    TACTIC_TIMEOUT = "TACTIC_TIMEOUT"
    PROOF_FAILED = "PROOF_FAILED"
    CERTIFIED = "CERTIFIED"

