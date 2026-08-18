from prometheus_client import Counter, Histogram

NODE_DURATION = Histogram(
    "agent_node_duration_seconds",
    "Time spent per graph node",
    ["node"],
)

NODE_OUTCOMES = Counter(
    "agent_node_outcomes_total",
    "Node completions by outcome",
    ["node", "success"],
)

CHAT_REQUEST_DURATION = Histogram(
    "chat_request_duration_seconds",
    "End-to-end /chat latency",
)

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total /chat requests",
    ["success"],
)

CHAT_ATTEMPTS = Histogram(
    "chat_attempts",
    "generate/validate/execute attempts per request",
    buckets=[1, 2, 3, 4],
)
