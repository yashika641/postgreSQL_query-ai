import json
import logging
import time
from functools import wraps
from pathlib import Path

from rich.logging import RichHandler

from .metrics import (
    CHAT_ATTEMPTS,
    CHAT_REQUEST_DURATION,
    CHAT_REQUESTS,
    NODE_DURATION,
    NODE_OUTCOMES,
)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("query_ai")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_DIR / "agent.log")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

    console_handler = RichHandler(rich_tracebacks=True)
    logger.addHandler(console_handler)


def log_node(node_name: str):
    """Decorator for LangGraph node functions: times the node, logs a
    structured JSON record, and records Prometheus metrics for it."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(state):
            start = time.perf_counter()
            result = fn(state)
            duration_s = time.perf_counter() - start

            success = result.get("error") is None
            attempt = result.get("attempts", state.get("attempts"))

            logger.info(json.dumps({
                "event": "node_complete",
                "node": node_name,
                "duration_ms": round(duration_s * 1000, 1),
                "attempt": attempt,
                "success": success,
                "error": result.get("error"),
            }))

            NODE_DURATION.labels(node=node_name).observe(duration_s)
            NODE_OUTCOMES.labels(node=node_name, success=str(success)).inc()

            return result
        return wrapper
    return decorator


def log_chat_request(question, thread_id, duration_ms, attempts, success, error=None):
    logger.info(json.dumps({
        "event": "chat_request",
        "thread_id": thread_id,
        "question": question,
        "duration_ms": round(duration_ms, 1),
        "attempts": attempts,
        "success": success,
        "error": error,
    }))

    CHAT_REQUEST_DURATION.observe(duration_ms / 1000)
    CHAT_REQUESTS.labels(success=str(success)).inc()
    CHAT_ATTEMPTS.observe(attempts)
