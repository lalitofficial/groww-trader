"use client";

import { Bot, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { fireCommentaryManual } from "@/lib/api";

type Message = {
  id?: number;
  role: string;
  content: string;
  payload?: Record<string, any>;
  created_at?: string;
};

type Props = {
  symbol: string | null;
};

export function AiCommentaryStream({ symbol }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setMessages([]);
  }, [symbol]);

  async function commentNow() {
    if (!symbol) return;
    setBusy(true);
    setError("");
    try {
      const result = await fireCommentaryManual({ symbol });
      const message = result.message || result;
      setMessages((current) => [
        { role: "assistant", content: message.content, payload: message.payload, created_at: message.created_at },
        ...current,
      ]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Commentary failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel ai-commentary-stream">
      <div className="panel-header">
        <div>
          <Bot size={13} />
          <strong>AI commentary</strong>
        </div>
        <button type="button" className="btn btn-primary" disabled={!symbol || busy} onClick={commentNow}>
          <Send size={13} />
          Comment now
        </button>
      </div>
      <div className="panel-body stack">
        {error ? <div className="context-badge warning">{error}</div> : null}
        {!symbol ? (
          <div className="muted">Focus a pick to see live commentary.</div>
        ) : messages.length === 0 ? (
          <div className="muted">No commentary yet. It will appear here automatically on events + cadence.</div>
        ) : null}
        <ul>
          {messages.map((message, index) => (
            <li key={index} className={`commentary-item commentary-${verdictClass(message.content)}`}>
              <p>{message.content}</p>
              {message.payload?.trigger ? (
                <span className="muted">trigger: {message.payload.trigger}{message.payload.fallback ? " (fallback)" : ""}</span>
              ) : null}
              {message.created_at ? <span className="muted">{message.created_at}</span> : null}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function verdictClass(content: string) {
  const upper = content.toUpperCase();
  if (upper.includes("EXIT_NOW")) return "exit";
  if (upper.includes("BOOK_PARTIAL")) return "partial";
  if (upper.includes("TRAIL")) return "trail";
  if (upper.includes("WAIT")) return "wait";
  return "hold";
}
