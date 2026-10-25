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
import mutmut
from hypothesis import given, strategies as st, assume, settings, example, errors, HealthCheck
import traceback
import z3



# def mutant_survival(mutfunc, prop, boundary):
#     for m in boundary:
#         try:
#             z3_param = prop(m, mutfunc(m))
#             if z3.is_false(z3.simplify(z3_param)):
#                 return True
#         except Exception as e:
#             return True
#     return False


def generate_default_boundary(func):
    try:
        import inspect
        arg_count = len(inspect.signature(func).parameters)
    except Exception:
        arg_count = getattr(getattr(func, "__code__", None), "co_argcount", 1)

    if arg_count == 2:
        return [(0, 0), (1, 1), (1, 2), (2, 1), (5, 10), (10, 20), (100, 200)]
    elif arg_count == 3:
        return [(0, 0, 0), (1, 1, 1), (1, 2, 3), (5, 10, 15)]
    else:
        return [0, 1, 2, 5, 10, -1, [], [0], [1], [1, 2], [3, 2, 1], "", "test"]


def extract_mutant_callable(mutated_code, func_name=None):
    file_namespace = {"z3": z3}
    exec(mutated_code, file_namespace)
    if func_name and callable(file_namespace.get(func_name)):
        return file_namespace[func_name]

    import ast
    try:
        tree = ast.parse(mutated_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = file_namespace.get(node.name)
                if callable(fn):
                    return fn
    except Exception:
        pass

    for val in file_namespace.values():
        if callable(val) and val is not z3:
            return val
    return None


def mutant_survival(mutfunc, prop, boundary=None):
    if boundary is None:
        boundary = generate_default_boundary(mutfunc)

    if isinstance(prop, str):
        prop = eval(prop, {"z3": z3})

    for m in boundary:
        try:
            args = m if isinstance(m, tuple) else (m,)
            res = mutfunc(*args)
            try:
                z3_param = prop(*args, res)
            except TypeError:
                z3_param = prop(m, res)
            if z3.is_false(z3.simplify(z3_param)):
                return False  
        except Exception:
            return False  
    return True 
