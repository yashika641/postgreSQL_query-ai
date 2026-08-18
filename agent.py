#state

import pandas as pd
from pandas import DataFrame
from typing import TypedDict
from sqlalchemy import text
from pandas.errors import DatabaseError
from database import engine
from sql_safety import validate_sql, SQLSafetyError
from langgraph.graph import StateGraph, END
from sql_generator import generate_sql
from google.genai.errors import APIError
from typing import Annotated
import operator
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from observalibilty.evaluation.observability import log_node


MAX_ATTEMPTS = 3

#state schema

class AgentState(TypedDict):
    question:str
    sql: str|None
    validated_sql:str | None
    result: dict | None    # {"columns": [...], "rows": [...]} -- JSON-serializable, NOT a DataFrame.
                            # The SqliteSaver checkpointer persists the whole state after every
                            # step via msgpack, and a raw DataFrame isn't serializable that way --
                            # confirmed by a real "TypeError: Type is not msgpack serializable:
                            # DataFrame" crash on every successful query once memory was added.
    error : str| None
    attempts:int
    history: Annotated[list,operator.add]

#nodes

# Each node: takes the current state dict, returns a dict of the fields
# it changed (LangGraph merges this into state — you don't mutate in place).

@log_node("generate")
def generate_node(state:AgentState)-> dict:
    try:
        sql = generate_sql(state['question'], previous_error=state.get("error"), history=state.get("history",[]))
        return{
            'sql':sql,
            'attempts': state['attempts']+1,
            "error":None
        }
    except APIError as e:
        return {
            'attempts': state['attempts']+1,
            'error': f"SQL generation failed: {e}",
        }

@log_node("record_history")
def record_history_node(state: AgentState)-> dict:
    turn = {
        "question": state["question"],
        "sql": state["validated_sql"],
        "row_count": len(state["result"]["rows"])}
    return {"history":[turn]}
    
    
@log_node("validate")
def validate_node(state: AgentState)-> dict:
    try:
        validated= validate_sql(state['sql'])
        return {"validated_sql":validated,"error":None}

    except SQLSafetyError as e:
        return {"error":f"sql genearated failed safety validation due to {e}"}

@log_node("execute")
def execute_node(state: AgentState)-> dict:
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(state["validated_sql"]),conn)
        result = {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
        return {'result':result,"error":None}

    except DatabaseError as e:
        return {'error': f'database execution error:{e}'}

#conditional_headers

def after_generate(state: AgentState)-> str:
    if state['error'] is None:
        return "validate"

    if state['attempts']>= MAX_ATTEMPTS:
        return END
    return "generate"


def after_validate(state: AgentState)-> str:
    if state['error'] is None:
        return "execute"

    if state['attempts']>= MAX_ATTEMPTS:
        return END
    return "generate"


def after_execute(state: AgentState)-> str:
    if state['error'] is None:
        return "record_history"
    if state['attempts']>= MAX_ATTEMPTS:
        return END
    return "generate"

#building the graph

builder= StateGraph(AgentState)

builder.add_node("generate", generate_node)
builder.add_node("validate", validate_node)
builder.add_node("execute", execute_node)
builder.add_node("record_history", record_history_node)

builder.add_edge("record_history", END)


builder.set_entry_point("generate")

builder.add_conditional_edges(
    "generate",
    after_generate,
    {"validate":"validate","generate":"generate",END:END},
)

builder.add_conditional_edges(
    "validate",
    after_validate,
    {"execute":"execute","generate":"generate",END:END},
)

builder.add_conditional_edges(
    "execute",
    after_execute,
    {"record_history":"record_history",
     "generate":"generate",
     END:END},
)

checkpointer = SqliteSaver(sqlite3.connect("agent_memory.sqlite", check_same_thread=False))


app = builder.compile(checkpointer=checkpointer)

#-----public entry point -------
def run_question(question: str, thread_id: str)-> DataFrame:
    initial_state={
        'question':question,
        'sql':None,
        'validated_sql': None,
        'result': None,
        "error": None,
        'attempts': 0,
    }
    
    config= {"configurable":{"thread_id":thread_id}}

    final_state = app.invoke(initial_state, config=config)

    if final_state['result'] is None:
        raise RuntimeError(
            f"failed to execute the question after {MAX_ATTEMPTS} attempts "
            f"last error:{final_state['error']}"
        )
    return pd.DataFrame(final_state['result']['rows'], columns=final_state['result']['columns'])

#------smoke test----------
if __name__=="__main__":
    thread_id = "test-session-1"
    try:
        print(run_question("How many questions were posted in 2023?", thread_id))
        print(run_question("now show me the same thing but for 2022", thread_id))

    except RuntimeError as e:
        print (f'error: {e}')
