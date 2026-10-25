from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Annotated

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from src.state import PipelineState
from src.helpers import mutant_survival, extract_mutant_callable
from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
import mutmut
from hypothesis import given, strategies as st, assume, settings, example, errors, HealthCheck
import traceback
import z3
import inspect
import ast

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
        inv_fn = eval(z3_lambda_str, env) # check again

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



# def mut_check_tool(test_func, lambdas):
#     cont = mutmut.Context()
#     mutated, mut_count = mutmut.mutate_ast(test_func, cont)
# 
#     survived = []
# 
#     for m in range(0, mut_count):
#         file_namespace = {}
#         cont1 = mutmut.Context()
#         mutated1, mut_count1 = mutmut.mutate_ast(test_func, cont)


def mut_check_tool(test_func, lambdas, boundary=None):
    if callable(test_func):
        test_func_code = inspect.getsource(test_func)
    else:
        test_func_code = str(test_func)



    prop_list = []
    if isinstance(lambdas, (list, tuple)):
        for item in lambdas:
            if isinstance(item, dict) and "z3_lambda" in item:
                prop_list.append(item["z3_lambda"])
            else:
                prop_list.append(item)
    else:
        prop_list = [lambdas]

    context = mutmut.Context(source=test_func_code)
    _, _ = mutmut.mutate(context)

    survived = []
    killed = []

    for mutation_id in context.performed_mutation_ids:
        mut_ctx = mutmut.Context(source=test_func_code, mutation_id=mutation_id)
        mutated_code, _ = mutmut.mutate(mut_ctx)

        try:
            mutfunc = extract_mutant_callable(mutated_code)
            if not callable(mutfunc):
                killed.append(str(mutation_id))
                continue
        except Exception:
            killed.append(str(mutation_id))
            continue

        mutant_survived_all = True
        for prop in prop_list:
            if not mutant_survival(mutfunc, prop, boundary):
                mutant_survived_all = False
                break

        if mutant_survived_all:
            survived.append({
                "mutation_id": str(mutation_id),
                "mutated_code": mutated_code,
            })
        else:
            killed.append(str(mutation_id))

    total = len(context.performed_mutation_ids)
    killed_count = len(killed)
    survived_count = len(survived)
    mutation_score = (killed_count / total) if total > 0 else 1.0

    return {
        "status": "PASSED" if survived_count == 0 else "FAILED",
        "total_mutants": total,
        "killed_mutants": killed_count,
        "survived_mutants": survived_count,
        "mutation_score": mutation_score,
        "survived": survived,
    }
