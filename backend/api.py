from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import make_asgi_app
import time
import uuid

from agent import app as agent_app
from observalibilty.evaluation.observability import log_chat_request

app= FastAPI()
app.mount("/metrics", make_asgi_app())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=['*'],
    allow_headers=['*'],
)


class chatrequest(BaseModel):
    question:str
    thread_id:str | None=None
    
class chatresponse(BaseModel):
    thread_id :str
    sql: str | None
    columns : list[str]
    rows: list[dict]
    rows_count:int
    
@app.post('/chat', response_model=chatresponse)
def chat(request:chatrequest):
    start = time.perf_counter()
    thread_id = request.thread_id or str(uuid.uuid4())

    initial_state = {
        'question': request.question,
        'sql': None,
        'validated_sql': None,
        'result':None,
        'error': None,
        'attempts':0,
    }

    config= {'configurable': {'thread_id':thread_id}}

    final_state = agent_app.invoke(initial_state,config=config)
    duration_ms = (time.perf_counter() - start) * 1000

    if final_state['result'] is None:
        log_chat_request(request.question, thread_id, duration_ms,
                          final_state['attempts'], success=False, error=final_state['error'])
        raise HTTPException(status_code=422, detail=final_state['error'])

    result = final_state['result']

    log_chat_request(request.question, thread_id, duration_ms,
                      final_state['attempts'], success=True)

    return chatresponse(
        thread_id = thread_id,
        sql = final_state['validated_sql'],
        columns= result['columns'],
        rows= result['rows'],
        rows_count=len(result['rows'])
    )
    
@app.get('/health')
def health():
    return {'status':"ok"}

