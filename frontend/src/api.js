const API_BASE = "http://localhost:8000";

export async function sendMessage(question, threadId) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, thread_id: threadId }),
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const errorBody = await response.json();
      detail = errorBody.detail || detail;
    } catch {
      // response wasn't JSON, fall back to the generic message
    }
    throw new Error(detail);
  }

  return response.json(); // { thread_id, sql, columns, rows, rows_count }
}
