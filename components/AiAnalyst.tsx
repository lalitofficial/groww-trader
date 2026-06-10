"use client";

import { Bot, Clock3, RefreshCw, Send, Square, ThumbsDown, ThumbsUp } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { getRequestBudget } from "@/lib/api";
import type { RequestBudget, StockAnalysis } from "@/lib/types";

type AiTaskType = "stock_report" | "resistance_read" | "account_risk" | "alert_explain" | "intraday_plan" | "daily_brief" | "strategy_compare";

type CachedReport = {
  id: number;
  content: string;
  model?: string | null;
  updated_at?: string;
};

type Thread = {
  id: number;
  title: string;
  active: number;
  updated_at?: string;
};

type AiMessage = {
  id?: number;
  role: "user" | "assistant" | "tool";
  content: string;
  payload?: Record<string, any>;
};

type ToolEvent = {
  tool: string;
  payload: Record<string, any>;
  kind: "call" | "result";
};

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export function AiAnalyst({ analysis }: { analysis: StockAnalysis }) {
  const [taskType, setTaskType] = useState<AiTaskType>("intraday_plan");
  const [report, setReport] = useState("");
  const [reports, setReports] = useState<CachedReport[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadId, setThreadId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [cacheState, setCacheState] = useState("");
  const [feedback, setFeedback] = useState<{ positive_pct: number | null; count: number } | null>(null);
  const [budget, setBudget] = useState<RequestBudget | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadReports = useCallback(async (hydrateReport = true) => {
    const response = await fetch(`/api/ai/report?symbol=${encodeURIComponent(analysis.symbol)}&limit=8&task_type=${taskType}`);
    const data = await response.json();
    const items = data.items || [];
    setReports(items);
    if (hydrateReport) setReport(items[0]?.content || "");
  }, [analysis.symbol, taskType]);

  const loadThreads = useCallback(async () => {
    const response = await fetch(`${backendUrl}/api/ai/threads?symbol=${encodeURIComponent(analysis.symbol)}&task_type=${encodeURIComponent(taskType)}`, { cache: "no-store" });
    const data = await response.json();
    const items = data.items || [];
    const active = data.active || items[0] || null;
    setThreads(items);
    setThreadId(active?.id || null);
    if (active?.id) await loadMessages(active.id);
  }, [analysis.symbol, taskType]);

  const loadFeedback = useCallback(async () => {
    const response = await fetch(`${backendUrl}/api/ai/feedback/summary?task_type=${encodeURIComponent(taskType)}&prompt_version=intraday-analyst-v4`, { cache: "no-store" });
    if (response.ok) setFeedback(await response.json());
  }, [taskType]);

  const loadBudget = useCallback(async () => {
    try {
      setBudget(await getRequestBudget());
    } catch {
      setBudget(null);
    }
  }, []);

  useEffect(() => {
    setReport("");
    setMessages([]);
    setToolEvents([]);
    void loadReports();
    void loadThreads();
    void loadFeedback();
    void loadBudget();
  }, [loadBudget, loadFeedback, loadReports, loadThreads]);

  async function loadMessages(nextThreadId: number) {
    const response = await fetch(`${backendUrl}/api/ai/messages?thread_id=${nextThreadId}&limit=20`, { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    setMessages((data.items || []).filter((item: AiMessage) => item.role === "user" || item.role === "assistant"));
  }

  async function generateReport(force = false) {
    setLoading(true);
    setReport("");
    setCacheState("");
    try {
      const response = await fetch("/api/ai/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis, force, task_type: taskType }),
      });
      const data = await response.json();
      setReport(data.content || data.error || "No report returned.");
      setCacheState(data.cached ? "Loaded from matching context cache." : data.context_hash ? `Fresh report saved (${data.context_hash}).` : "");
      await loadReports(false);
      await loadBudget();
    } finally {
      setLoading(false);
    }
  }

  async function newThread() {
    const response = await fetch(`${backendUrl}/api/ai/threads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: analysis.symbol, task_type: taskType, title: `${analysis.symbol} ${AI_TASKS.find((task) => task.value === taskType)?.label}` }),
    });
    const data = await response.json();
    setThreadId(data.item?.id || null);
    setMessages([]);
    await loadThreads();
  }

  async function clearThread() {
    if (!threadId) return;
    await fetch(`${backendUrl}/api/ai/threads/${threadId}/clear`, { method: "POST" });
    setMessages([]);
  }

  async function askStream() {
    if (!question.trim() || streaming) return;
    const prompt = question.trim();
    setQuestion("");
    setStreaming(true);
    setToolEvents([]);
    const controller = new AbortController();
    abortRef.current = controller;
    setMessages((items) => [...items, { role: "user", content: prompt }, { role: "assistant", content: "" }]);
    try {
      const response = await fetch("/api/ai/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis, question: prompt, activeReport: report, task_type: taskType, thread_id: threadId }),
        signal: controller.signal,
      });
      const reader = response.body?.getReader();
      if (!reader) throw new Error("No stream returned.");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {
          const line = frame.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "token") {
            setMessages((items) => updateStreamingAssistant(items, event.delta || ""));
          } else if (event.type === "tool_call") {
            setToolEvents((items) => [...items, { tool: event.tool, payload: event.payload || {}, kind: "call" }]);
          } else if (event.type === "tool_result") {
            setToolEvents((items) => [...items, { tool: event.tool, payload: event.payload || {}, kind: "result" }]);
          } else if (event.type === "done") {
            setThreadId(event.thread_id || threadId);
            setMessages((items) => finalizeAssistant(items, event.payload?.content || "", event.message_id));
          } else if (event.type === "error") {
            setMessages((items) => updateStreamingAssistant(items, event.error || "AI stream failed."));
          }
        }
      }
      await loadBudget();
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  async function vote(messageId: number | undefined, rating: 1 | -1) {
    await fetch(`${backendUrl}/api/ai/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: messageId, symbol: analysis.symbol, task_type: taskType, rating, prompt_version: "intraday-analyst-v4" }),
    });
    await loadFeedback();
  }

  const azureUsage = budget?.token_usage?.azure_openai;

  return (
    <section className="panel ai-thread-panel">
      <div className="panel-header">
        <div>
          <strong>GPT Analyst</strong>
          <div className="muted">Threads, tools, streaming, cache</div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={() => generateReport(false)} disabled={loading || streaming}>
            <Bot size={14} />
            Cached
          </button>
          <button type="button" className="btn btn-primary" onClick={() => generateReport(true)} disabled={loading || streaming}>
            <RefreshCw size={14} />
            Fresh
          </button>
        </div>
      </div>
      <div className="panel-body stack compact-panel-body">
        <div className="ai-task-tabs">
          {AI_TASKS.map((task) => (
            <button key={task.value} type="button" className={taskType === task.value ? "active" : ""} onClick={() => setTaskType(task.value)}>
              {task.label}
            </button>
          ))}
        </div>
        <div className="ai-thread-toolbar">
          <select value={threadId || ""} onChange={(event) => {
            const id = Number(event.target.value);
            setThreadId(id);
            void loadMessages(id);
          }}>
            {threads.map((thread) => (
              <option key={thread.id} value={thread.id}>
                {thread.title || `Thread ${thread.id}`}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-secondary" onClick={newThread}>+ new thread</button>
          <button type="button" className="btn btn-secondary" onClick={clearThread} disabled={!threadId}>Clear</button>
        </div>
        {feedback?.count ? <div className="context-badge">this prompt variant: {feedback.positive_pct ?? 0}% positive (n={feedback.count})</div> : null}
        {cacheState ? <div className="context-badge">{cacheState}</div> : null}
        <div className="report-history">
          <div className="history-title">
            <Clock3 size={14} />
            <span>{reports.length} saved reports</span>
          </div>
          {reports.map((item) => (
            <button key={item.id} type="button" className="history-chip" onClick={() => setReport(item.content)}>
              <span>{item.updated_at ? new Date(item.updated_at).toLocaleString() : "Cached"}</span>
              <strong>{item.model || "GPT"}</strong>
            </button>
          ))}
        </div>
        {loading && !report ? (
          <div className="ai-report">Building analyst context, checking cache, and thinking through the setup...</div>
        ) : report ? (
          <div className="ai-report">
            <MarkdownView content={report} />
          </div>
        ) : (
          <div className="ai-report">Generate a structured {AI_TASKS.find((task) => task.value === taskType)?.label.toLowerCase()} read for this stock.</div>
        )}

        <div className="ai-chat-feed">
          {messages.map((message, index) => (
            <article key={`${message.role}-${message.id || index}`} className={`ai-bubble ${message.role}`}>
              <MarkdownView content={message.content || (message.role === "assistant" && streaming ? "Thinking..." : "")} />
              {message.role === "assistant" && message.content ? (
                <div className="ai-feedback">
                  <button type="button" onClick={() => vote(message.id, 1)} title="Helpful"><ThumbsUp size={13} /></button>
                  <button type="button" onClick={() => vote(message.id, -1)} title="Not helpful"><ThumbsDown size={13} /></button>
                </div>
              ) : null}
            </article>
          ))}
          {toolEvents.length ? <ToolEvents events={toolEvents} /> : null}
        </div>

        <div className="field">
          <label>Ask follow-up</label>
          <textarea className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} placeholder="What would invalidate this setup?" />
        </div>
        <div className="ai-chat-actions">
          <button type="button" className="btn btn-primary w-fit" onClick={askStream} disabled={streaming || !question.trim()}>
            <Send size={14} />
            Ask
          </button>
          {streaming ? (
            <button type="button" className="btn btn-secondary w-fit" onClick={() => abortRef.current?.abort()}>
              <Square size={14} />
              Stop
            </button>
          ) : null}
        </div>
        <div className="ai-quota-footer">
          Used {budget?.total ?? 0} source/tool calls in the last hour
          {azureUsage ? `, ${(azureUsage.total_tokens / 1000).toFixed(1)}k Azure tokens` : ""}
        </div>
      </div>
    </section>
  );
}

const AI_TASKS: Array<{ value: AiTaskType; label: string }> = [
  { value: "intraday_plan", label: "Intraday" },
  { value: "stock_report", label: "Swing" },
  { value: "daily_brief", label: "Daily brief" },
  { value: "strategy_compare", label: "Strategies" },
  { value: "resistance_read", label: "Levels" },
  { value: "account_risk", label: "Risk" },
  { value: "alert_explain", label: "Alerts" },
];

function updateStreamingAssistant(items: AiMessage[], delta: string) {
  const next = [...items];
  const last = next[next.length - 1];
  if (last?.role === "assistant") last.content += delta;
  return next;
}

function finalizeAssistant(items: AiMessage[], content: string, id?: number) {
  const next = [...items];
  const last = next[next.length - 1];
  if (last?.role === "assistant") {
    last.content = content || last.content;
    last.id = id;
  }
  return next;
}

function ToolEvents({ events }: { events: ToolEvent[] }) {
  return (
    <div className="ai-tool-events">
      {events.map((event, index) => (
        <div key={`${event.kind}-${event.tool}-${index}`} className={`ai-tool-event ${event.kind}`}>
          <strong>{event.kind === "call" ? "Tool" : "Result"} · {event.tool}</strong>
          <pre>{JSON.stringify(compactPayload(event.payload), null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}

function compactPayload(value: Record<string, any>) {
  if (Array.isArray(value?.results)) return { results: value.results.slice(0, 4) };
  if (Array.isArray(value?.strikes)) return { summary: value.summary, strikes: value.strikes.slice(0, 5) };
  if (Array.isArray(value?.items)) return { items: value.items.slice(0, 5) };
  return value;
}
