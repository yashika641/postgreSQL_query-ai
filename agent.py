#state

import pandas as pd
from pandas import DataFrame
from typing import TypedDict
from sqlalchemy import text
from pandas.errors import DatabaseError
from database import engine
from sql_safety import validate_sql, SQLSafetyError
from langgraph.graph import StateGraph, END
from sql_generator import generate_sql, SQLGenerationError , MAX_VERBATIM_TURNS, summarize_turn
from google.genai.errors import APIError
from visualization.chart_builder import build_chart
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
    history_summary : str | None
    history_folded_count: int
    chart: dict | None     # {"chart_type", "x_column", "y_column", "image_base64"} from
                            # visualize_node, or None if the result wasn't chart-worthy.

#nodes

# Each node: takes the current state dict, returns a dict of the fields
# it changed (LangGraph merges this into state — you don't mutate in place).

@log_node("generate")
def generate_node(state:AgentState)-> dict:
    try:
        sql = generate_sql(state['question'], previous_error=state.get("error"), history=state.get("history",[])[-MAX_VERBATIM_TURNS:],history_summary= state.get("history_summary"),
                           )
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
    except SQLGenerationError as e:
        return {
            "attempts": state['attempts']+1,
            "error": "sql generation failed (unexpectedly): " + str(e)
            }
            
    except Exception as e:
        '''-- NEW: catches whatever APIError doesn't (timeouts, network errors,
        -- other SDK-internal exceptions) so the graph retries through the
        -- normal after_generate router instead of crashing uncaught.
        -- Must come AFTER the APIError clause -- Python matches except
        -- blocks top-to-bottom, and Exception would otherwise swallow
        -- APIError too, silently losing the more specific error message.'''
        return {
            "attempts": state["attempts"] + 1,
            "error": "SQL generation failed (unexpected): " + str(e)
        }
    

@log_node("visualize")
def visualize_node(state: AgentState)-> dict:
    # Charting is a heuristic add-on, not part of the answer itself -- a
    # failure here should never break the pipeline; the user still gets
    # their tabular result even if the chart heuristics choke on unusual
    # data.
    try:
        chart = build_chart(state["question"], state["result"])
    except Exception:
        chart = None
    return {"chart": chart}


@log_node("record_history")
def record_history_node(state: AgentState)-> dict:
    turn = {
        "question": state["question"],
        "sql": state["validated_sql"],
        "row_count": len(state["result"]["rows"])}
    old_history = state['history']
    folded_count = state.get("history_folded_count", 0)
    total_after = len(old_history)+1
    summary = state.get('history_summary')
    
    if total_after> MAX_VERBATIM_TURNS and folded_count< total_after-MAX_VERBATIM_TURNS:
        turn_to_fold = old_history[folded_count]
        summary = summarize_turn(summary, turn_to_fold)
        folded_count +=1
        return {"history":[turn],"history_summary":summary,"history_folded_count":folded_count}
    
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
        return "visualize"
    if state['attempts']>= MAX_ATTEMPTS:
        return END
    return "generate"

#building the graph

builder= StateGraph(AgentState)

builder.add_node("generate", generate_node)
builder.add_node("validate", validate_node)
builder.add_node("execute", execute_node)
builder.add_node("visualize", visualize_node)
builder.add_node("record_history", record_history_node)

builder.add_edge("visualize", "record_history")
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
    {"visualize":"visualize",
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
        'chart': None,
        "history_summary": None,
        "history_folded_count":0
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
