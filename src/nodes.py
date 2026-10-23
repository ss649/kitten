from __future__ import annotations

import ast
import json
import logging
import os
import re
from typing import Any, Dict, List, Literal
from groq import Groq
from z3 import Solver, Int, Real, Bool, Const, SeqSort, IntSort, Length
# client = Groq()
from google import genai
from google.genai import types
from langchain_core.messages import AIMessage, HumanMessage

from src.state import (
    PipelineStage,
    PipelineState,
    VerificationStatus,
)
from src.tools import pbt_execute_tool, smt_verify_tool

logger = logging.getLogger(__name__)


def basic_pbt_node(state):
    logger.info("Executing basic_pbt_node ....")
    generated_properties = state.get("verified_properties", [])
    if not generated_properties:
        logger.warning("No Z3-verified properties found to run PBT on.")
        return {
            "stage": PipelineStage.FAILED,
            "pbt_results": [],
            "verification_status": VerificationStatus.FAILED,
            "error": "No properties passed Z3 formal verification",
        }

    pbt_results = []
    all_passed = True
    try:
        for prop in generated_properties:
            func_name = prop.get("function_name", "unknown")
            prop_name = prop.get("property_name", "")
            test_code = prop.get("test_code", "")

            result = pbt_execute_tool(test_code)
            result["function_name"] = func_name
            result["property_name"] = prop_name
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
    logger.info("Generating properties for extracted functions as Z3-Python Lambda invariants...")

    extracted_functions = state.get("extracted_functions", [])
    generated_properties = []

    try:


        gemini_api_key = os.getenv("SGEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("Environment variable SGEMINI_API_KEY (or GEMINI_API_KEY) must be set.")
        client = genai.Client(api_key=gemini_api_key)
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

        for func in extracted_functions:
            func_name = func.get("name", "")
            func_code = func.get("code", "")
            func_doc = func.get("docstring", "")

            prompt = (
                "You are an expert in Formal Verification and Property-Based Testing in Python using Z3 and Hypothesis.\n"
                f"Given the following Python function:\n\n"
                f"```python\n{func_code}\n```\n\n"
                f"Docstring: {func_doc}\n\n"
                "Generate 2 concise properties as Z3-Python Lambda invariants for this function, along with corresponding Hypothesis tests.\n"
                "Requirements:\n"
                "1. Each property must specify an invariant expressed as an executable Z3-Python lambda function.\n"
                "   - For numerical functions, use Z3 constructs (z3.Implies, z3.And, z3.Or, etc.) over input arguments and output 'res'.\n"
                "   - For sequence/list functions, express properties over lengths (e.g. lambda xs, res: z3.Length(res) == z3.Length(xs)). Avoid z3.Reverse.\n"
                "2. Provide an executable, concise standalone Hypothesis test for each invariant including the target function definition and @given decorator.\n"
                "3. Output ONLY a valid JSON list of objects with the following schema:\n"
                "[\n"
                "  {\n"
                f'    "function_name": "{func_name}",\n'
                '    "property_name": "descriptive_name",\n'
                '    "z3_lambda": "lambda a, b, res: z3.Implies(z3.And(a >= 0, b >= 0), res == a + b)",\n'
                '    "z3_vars": [{"name": "a", "sort": "Int"}, {"name": "b", "sort": "Int"}, {"name": "res", "sort": "Int"}],\n'
                '    "hypothesis_test_code": "from hypothesis import given, strategies as st\\n\\n..."\n'
                "  }\n"
                "]\n"
            )

            # Groq implementation (commented out)
            # model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            # chat_completion = client.chat.completions.create(
            #     model=model_name,
            #     messages=[
            #         {
            #             "role": "system",
            #             "content": "You are an expert in Formal Verification and Property-Based Testing in Python using Z3 and Hypothesis. Always output valid JSON only.",
            #         },
            #         {
            #             "role": "user",
            #             "content": prompt,
            #         },
            #     ],
            #     temperature=0.2,
            #     max_tokens=4096,
            # )
            # raw_text = chat_completion.choices[0].message.content or ""

            # Gemini implementation using SGEMINI_API_KEY
            raw_text = ""
            for attempt in range(4):
                try:
                    gemini_response = client.models.generate_content(
                        model=gemini_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        ),
                    )
                    raw_text = gemini_response.text or ""
                    break
                except Exception as api_err:
                    if ("503" in str(api_err) or "UNAVAILABLE" in str(api_err)) and attempt < 3:
                        import time
                        time.sleep(2 * (attempt + 1))
                        continue
                    raise api_err

            cleaned_json = raw_text.strip()
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", cleaned_json, re.DOTALL)
            if match:
                cleaned_json = match.group(1).strip()
            elif cleaned_json.startswith("```"):
                lines = cleaned_json.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_json = "\n".join(lines).strip()

            try:
                parsed_list = json.loads(cleaned_json)
                for item in parsed_list:
                    generated_properties.append({
                        "function_name": func_name,
                        "property_name": item.get("property_name", "unnamed"),
                        "z3_lambda": item.get("z3_lambda", ""),
                        "z3_vars": item.get("z3_vars", []),
                        "test_code": item.get("hypothesis_test_code", ""),
                    })
            except Exception as parse_err:
                logger.error("Failed to parse JSON for function '%s': %s", func_name, parse_err)

        result = {
            "stage": PipelineStage.PBT,
            "generated_properties": generated_properties,
        }
        logger.info(
            "property_generate_node completed successfully. Generated %d Z3 lambda properties for functions: %s",
            len(generated_properties),
            [p.get("function_name") for p in generated_properties],
        )
        for idx, prop in enumerate(generated_properties, start=1):
            logger.debug(
                "Generated Z3 property [%d/%d] '%s' for '%s':\nLambda: %s\nTest Code:\n%s",
                idx,
                len(generated_properties),
                prop.get("property_name"),
                prop.get("function_name"),
                prop.get("z3_lambda"),
                prop.get("test_code"),
            )
        return result

    except Exception as e:
        logger.error(f"Error generating properties: {e}", exc_info=True)
        failure_result = {
            "stage": PipelineStage.FAILED,
            "error": str(e),
        }
        logger.warning("property_generate_node returning failure: %s", failure_result)
        return failure_result


def soundness_gate_node(state):
    logger.info("Executing soundness_gate_node...")

    generated_properties = state.get("generated_properties", [])

    verified_properties = []
    refuted_properties = []
    undecided_properties = []

    try:
        for prop in generated_properties:
            func_name = prop.get("function_name", "unknown")
            prop_name = prop.get("property_name", "unnamed")
            z3_lambda_str = prop.get("z3_lambda", "")
            z3_vars = prop.get("z3_vars", [])

            smt_result = smt_verify_tool(z3_lambda_str, z3_vars, func_name)
            status = smt_result.get("status")

            if status in ("PROVEN_VALID", "SATISFIABLE"):
                logger.info("Z3 verified (%s): [%s] %s", status, func_name, prop_name)
                verified_properties.append({**prop, "formal_status": status})
            elif status == "REFUTED":
                logger.warning("Z3 refuted: [%s] %s (%s)", func_name, prop_name, smt_result.get("counterexample"))
                refuted_properties.append({**prop, "formal_status": status, "counterexample": smt_result.get("counterexample")})
            else:
                logger.info("Z3 undecided/error for [%s] %s: %s", func_name, prop_name, smt_result.get("error_message"))
                undecided_properties.append({**prop, "formal_status": status, "error": smt_result.get("error_message")})

        logger.info(
            "soundness_gate_node completed: %d verified, %d refuted, %d undecided",
            len(verified_properties),
            len(refuted_properties),
            len(undecided_properties),
        )

        return {
            "stage": PipelineStage.SOUNDNESS_GATE,
            "verified_properties": verified_properties,
            "refuted_properties": refuted_properties,
            "undecided_properties": undecided_properties,
        }

    except Exception as e:
        logger.error(f"Error during soundness gate verification: {e}", exc_info=True)
        return {
            "stage": PipelineStage.FAILED,
            "verification_status": VerificationStatus.FAILED,
            "error": str(e),
        }
