from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, HumanMessage

from src.state import (
    PipelineStage,
    PipelineState,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


def basic_pbt_node(state: PipelineState) -> Dict[str, Any]:

    logger.info("Executing run_pbt_node")

    try:
        # TODO: Fix parsing of PBT code
        pbt_results: List[Any] = []

        return {
            "stage": PipelineStage.PLAUSIBLE_PBT,
            "pbt_results": pbt_results,
            "verification_status": VerificationStatus.PENDING,
        }

    except Exception as e:
        logger.error(f"Error during PBT execution: {e}", exc_info=True)
        return {
            "stage": PipelineStage.FAILED,
            "verification_status": VerificationStatus.PROOF_FAILED,
            "error": str(e),
        }


def parse_python_file_node(state: PipelineState) -> Dict[str, Any]:

    logger.info("Initial parsing ....")

    file_path = state.get("file_path", "")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code, filename=file_path)

        extracted_functions: List[Dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                extracted_functions.append({
                    "name": node.name,
                    "code": ast.unparse(node),
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node) or "",
                })

        return {
            "stage": PipelineStage.PARSING,
            "extracted_functions": extracted_functions,
        }

    except Exception as e:
        logger.error(f"Error parsing Python file '{file_path}': {e}", exc_info=True)
        return {
            "stage": PipelineStage.FAILED,
            "error": str(e),
        }
