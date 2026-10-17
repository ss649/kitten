from __future__ import annotations

import ast
import logging
import os
import re
from typing import Any, Dict, List, Literal
from groq import Groq

from langchain_core.messages import AIMessage, HumanMessage

from src.state import (
    PipelineStage,
    PipelineState,
    VerificationStatus,
)
from src.tools import pbt_execute_tool

logger = logging.getLogger(__name__)


def basic_pbt_node(state):
    logger.info("Executing run_pbt_node ....")
    generated_properties = state.get("generated_properties", [])
    pbt_results = []
    all_passed = True
    try:
        for prop in generated_properties:
            func_name = prop.get("function_name", "unknown")
            test_code = prop.get("test_code", "")

            result = pbt_execute_tool(test_code)
            result["function_name"] = func_name
            pbt_results.append(result)

            if result.get("status") != "PASSED":
                all_passed = False

        status = VerificationStatus.PASSED if (all_passed and pbt_results) else VerificationStatus.FAILED

        return {
            "stage": PipelineStage.COMPLETED if all_passed else PipelineStage.FAILED,
            "pbt_results": pbt_results,
            "verification_status": status,
        }

    except Exception as e:
        logger.error(f"Error during PBT execution: {e}", exc_info=True)
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
        # from google import genai
        # # specifics
        # client = genai.Client()

        # specifics
        # client = Groq(api_key="your_api_key_here")
        client = Groq()

        for func in extracted_functions:
            func_name = func.get("name", "")
            func_code = func.get("code", "")
            func_doc = func.get("docstring", "")

            prompt = (
                "You are an expert in Property-Based Testing in Python using Hypothesis.\n"
                f"Given the following Python function:\n\n"
                f"```python\n{func_code}\n```\n\n"
                f"Docstring: {func_doc}\n\n"
                "Write a standalone Property-Based Test in Python using Hypothesis.\n"
                "Requirements:\n"
                "1. Include the exact function definition above.\n"
                "2. Define a test function starting with 'test_'.\n"
                "3. Decorate the test function with @given(...) using strategies from `st` (e.g. st.integers(), st.lists(...)).\n"
                "4. Output ONLY valid, executable Python code with no markdown formatting or extra text.\n"
            )

            # response = client.models.generate_content(
            #     model="gemini-2.5-flash",
            #     contents=prompt,
            # )
            # raw_text = response.text or ""

            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            chat_completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in Property-Based Testing in Python using Hypothesis.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
            )
            raw_text = chat_completion.choices[0].message.content or ""

            cleaned_code = raw_text.strip()
            match = re.search(r"```(?:python)?\s*\n(.*?)\n```", cleaned_code, re.DOTALL)
            if match:
                cleaned_code = match.group(1).strip()
            elif cleaned_code.startswith("```"):
                lines = cleaned_code.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_code = "\n".join(lines).strip()

            generated_properties.append({
                "function_name": func_name,
                "test_code": cleaned_code,
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
