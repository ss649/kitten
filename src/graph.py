import os
from __future__ import annotations
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

def build_pipeline_graph():
    builder = StateGraph(PipelineState)

    builder.add_node("parse_python_file", parse_python_file_node)
    builder.add_node("basic_pbt", basic_pbt_node)
    builder.add_edge(START, "parse_python_file")
    builder.add_edge("parse_python_file", "basic_pbt")
    builder.add_edge("basic_pbt", END)

    return builder


def compile_pipeline_graph(checkpointer):
    builder = build_pipeline_graph()
    memory = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=memory)


graph = compile_pipeline_graph()
