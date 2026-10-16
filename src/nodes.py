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
from src.tools import pbt_execute_tool

logger = logging.getLogger(__name__)


def basic_pbt_node(state: PipelineState):

    logger.info("Executing run_pbt_node ....")

    try:
        pbt_execute_tool()
        pbt_results = []
        return {
            "stage": PipelineStage.PBT,
            "pbt_results": pbt_results,
            "verification_status": VerificationStatus.PENDING,
        }

    except Exception as e:
        logger.error("Error during PBT execution: "+e, exc_info=True)
        return {
            "stage": PipelineStage.FAILED,
            "verification_status": VerificationStatus.FAILED,
            "error": str(e),
        }


def parse_python_file_node(state: PipelineState):

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


def property_generate_node(state):
    logger.info("Generating properties for extracted functions...")

    extracted_functions = state.get("extracted_functions", [])
    generated_properties = []

    try:
        #TInitialize LLM client

        for func in extracted_functions:
            func_name = func.get("name", "")
            func_code = func.get("code", "")

            #Format prompt with func_name and func_code
            generated_properties.append({
                "function_name": func_name,
                "test_code": f"# TODO: generated hypothesis test for {func_name}",
            })

        return {
            "stage": PipelineStage.PBT,
            "generated_properties": generated_properties,
        }

    except Exception as e:
        logger.error(f"Error generating properties: {e}", exc_info=True)
        return {
            "stage": PipelineStage.FAILED,
            "error": str(e),
        }
