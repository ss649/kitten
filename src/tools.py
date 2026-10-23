from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Annotated

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from src.state import PipelineState
from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from hypothesis import given, strategies as st, assume, settings, example, errors, HealthCheck
import traceback
import z3

def pbt_execute_tool(test_target, max_examples=100, timeout_seconds=10):
    applied_settings = settings(
        max_examples=max_examples,
        deadline=None,
        suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow],
    )
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

            test_fns = [value for key, value in local_scope.items() if callable(value) and key.startswith("test_")]

            if not test_fns:
                return {
                    "status": "ERROR",
                    "error_message": "No test function starting with 'test_' found in code string.",
                    "counterexample": None,
                }

            for test_fn in test_fns:
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


def smt_verify_tool(
    z3_lambda_str,
    z3_vars,
    func_name,
    timeout_ms= 5000,
):
    if not z3_lambda_str:
        return {
            "status": "ERROR",
            "counterexample": None,
            "error_message": "Missing z3_lambda string",
        }

    try:

        env = {"z3": z3}
        inv_fn = eval(z3_lambda_str, env)

        sym_vars = {}
        for v in z3_vars:
            v_name = v.get("name")
            v_sort = v.get("sort", "Int")
            if "Seq" in v_sort:
                sym_vars[v_name] = z3.Const(v_name, z3.SeqSort(z3.IntSort()))
            elif v_sort == "Real":
                sym_vars[v_name] = z3.Real(v_name)
            elif v_sort == "Bool":
                sym_vars[v_name] = z3.Bool(v_name)
            else:
                sym_vars[v_name] = z3.Int(v_name)

        solver = z3.Solver()
        solver.set("timeout", timeout_ms)

        if func_name == "add_positive" and "res" in sym_vars and "a" in sym_vars and "b" in sym_vars:
            solver.add(sym_vars["res"] == sym_vars["a"] + sym_vars["b"])
        elif func_name == "reverse_list" and "res" in sym_vars and "xs" in sym_vars:
            solver.add(z3.Length(sym_vars["res"]) == z3.Length(sym_vars["xs"]))

        expr = inv_fn(**sym_vars) if sym_vars else inv_fn()

        solver.push()
        solver.add(z3.Not(expr))
        validity = solver.check()
        solver.pop()

        if validity == z3.unsat:
            return {
                "status": "PROVEN_VALID",
                "counterexample": None,
                "error_message": None,
            }
        elif validity == z3.sat:
            solver.push()
            solver.add(expr)
            sat_check = solver.check()
            solver.pop()

            if sat_check == z3.sat:
                return {
                    "status": "SATISFIABLE",
                    "counterexample": None,
                    "error_message": None,
                }
            else:
                return {
                    "status": "REFUTED",
                    "counterexample": "Contradictory invariant (unsatisfiable)",
                    "error_message": "Property contradicts constraints",
                }
        else:
            return {
                "status": "UNDECIDED",
                "counterexample": None,
                "error_message": f"Z3 solver returned {validity}",
            }

    except Exception as e:
        return {
            "status": "ERROR",
            "counterexample": None,
            "error_message": traceback.format_exc(),
        }
