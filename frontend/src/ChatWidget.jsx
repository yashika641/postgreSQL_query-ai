import { useEffect, useRef, useState } from "react";
import { sendMessage } from "./api";
import ResultTable from "./ResultTable";

const THREAD_STORAGE_KEY = "query_ai_thread_id";

function ChatWidget() {
  const [threadId, setThreadId] = useState(() =>
    localStorage.getItem(THREAD_STORAGE_KEY),
  );
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (threadId) localStorage.setItem(THREAD_STORAGE_KEY, threadId);
  }, [threadId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendMessage(question, threadId);
      setThreadId(result.thread_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          sql: result.sql,
          columns: result.columns,
          rows: result.rows,
          rowsCount: result.rows_count,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", error: err.message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleNewConversation() {
    localStorage.removeItem(THREAD_STORAGE_KEY);
    setThreadId(null);
    setMessages([]);
  }

  return (
    <div className="chat-widget">
      <header className="chat-header">
        <h1>Query AI</h1>
        <button
          type="button"
          className="new-conversation-btn"
          onClick={handleNewConversation}
          disabled={messages.length === 0}
        >
          New conversation
        </button>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="chat-empty-hint">
            Ask a question about the Stack Overflow database — e.g. "How many
            questions were posted in 2023?"
          </p>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`chat-bubble ${msg.role}${msg.error ? " error" : ""}`}
          >
            {msg.role === "user" && <p>{msg.text}</p>}

            {msg.role === "assistant" && msg.error && (
              <p className="error-text">{msg.error}</p>
            )}

            {msg.role === "assistant" && !msg.error && (
              <>
                {msg.sql && (
                  <details className="sql-details">
                    <summary>Generated SQL</summary>
                    <pre>{msg.sql}</pre>
                  </details>
                )}
                <ResultTable
                  columns={msg.columns}
                  rows={msg.rows}
                  rowsCount={msg.rowsCount}
                />
              </>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-bubble assistant loading">
            <p>Thinking…</p>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          rows={2}
          disabled={loading}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default ChatWidget;
