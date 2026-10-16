from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Annotated

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from src.nodes import basic_pbt_node, parse_python_file_node
from src.state import PipelineState
from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from hypothesis import given, strategies as st, assume, settings, example, errors
import traceback


def pbt_execute_tool(test_target, max_examples=100, timeout_seconds=10):
    applied_settings = settings(max_examples=max_examples, deadline=None)
    try:
        if callable(test_target):
            test_fn = applied_settings(test_target)
            test_fn()
        elif isinstance(test_target, str):
            local_scope = {
                "given": given,
                "st": st,
                "assume": assume,
                "settings": settings,
                "example": example,
            }
            exec(test_target, local_scope)

            test_fn = None
            for key, value in local_scope.items():
                if callable(value) and key.startswith("test_"):
                    test_fn = value
                    break

            if test_fn is None:
                return {
                    "status": "ERROR",
                    "error_message": "No test function starting with 'test_' found in code string.",
                    "counterexample": None,
                }

            configured_fn = applied_settings(test_fn)
            configured_fn()
        else:
            return {
                "status": "ERROR",
                "error_message": "test_target must be either a callable or a python code string.",
                "counterexample": None,
            }

        return {
            "status": "PASSED",
            "counterexample": None,
            "error_message": None,
        }

    except errors.Unsatisfiable as e:
        return {
            "status": "UNSATISFIABLE",
            "counterexample": None,
            "error_message": f"Hypothesis could not satisfy assumptions: {e}",
        }

    except AssertionError as e:
        return {
            "status": "FAILED",
            "counterexample": str(e),
            "error_message": traceback.format_exc(),
        }

    except Exception as e:
        return {
            "status": "FAILED",
            "counterexample": str(e),
            "error_message": traceback.format_exc(),
        }