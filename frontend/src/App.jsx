import { useEffect, useRef, useState } from "react";
import { askQuestion } from "./api.js";

function Message({ message }) {
  return (
    <div className={`message ${message.role}`}>
      <p>{message.content}</p>
      {message.sources?.length > 0 && (
        <details>
          <summary>Sources ({message.sources.length})</summary>
          {message.sources.map((source, i) => (
            <div className="source" key={i}>
              <strong>{source.category}</strong> — {source.question}{" "}
              <span className="score">({source.similarity.toFixed(2)})</span>
              <p>{source.text}</p>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const { answer, sources } = await askQuestion(question);
      setMessages((prev) => [...prev, { role: "assistant", content: answer, sources }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Something went wrong: ${err.message}`, error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Hotel FAQ Assistant</h1>
      <div className="messages">
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
        {loading && <div className="message assistant">Searching FAQ…</div>}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the hotel"
          maxLength={1000}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}
