from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Annotated

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from src.nodes import (
    basic_pbt_node,
    parse_python_file_node,
    property_generate_node,
    soundness_gate_node,
)
from src.state import PipelineState
from google.cloud import aiplatform
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

def build_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("parse_python_file", parse_python_file_node)
    builder.add_node("property_generate", property_generate_node)
    builder.add_node("soundness_gate", soundness_gate_node)
    builder.add_node("basic_pbt", basic_pbt_node)

    builder.add_edge(START, "parse_python_file")
    builder.add_edge("parse_python_file", "property_generate")
    builder.add_edge("property_generate", "soundness_gate")
    builder.add_edge("soundness_gate", "basic_pbt")
    builder.add_edge("basic_pbt", END)
    return builder


def compile_graph(checkpointer=None):
    builder = build_graph()
    if checkpointer is not None:
        memory = checkpointer 
    else:
        memory = MemorySaver()
    return builder.compile(checkpointer=memory)


graph = compile_graph()

