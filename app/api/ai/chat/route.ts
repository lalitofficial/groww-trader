import crypto from "crypto";
import { NextResponse } from "next/server";
import { runAzureChatCompletion, type AzureChatMessage } from "@/lib/ai";
import { AI_TOOLS, executeAiTool } from "@/lib/ai-tools";
import { ANALYST_PROMPT_VERSION, buildChatPrompt, buildTaskContext, chatSystemPrompt, contextHash, type AiTaskType } from "@/lib/ai-context";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const MAX_TOOL_ROUNDS = 4;

export async function POST(request: Request) {
  try {
    const { analysis, question, activeReport, task_type = "stock_report", thread_id } = await request.json();
    if (!analysis?.symbol || !question?.trim()) {
      return NextResponse.json({ error: "analysis.symbol and question are required." }, { status: 400 });
    }
    const taskType = validTaskType(task_type);
    const context = buildTaskContext(analysis, taskType);
    const thread = thread_id ? { id: thread_id } : await ensureThread(analysis.symbol, taskType);
    const prior = await loadMessages(thread.id);
    const cacheKey = chatCacheKey(analysis.symbol, taskType, question, contextHash(context));
    const cached = await getCache("chat", cacheKey);
    await saveMessage(thread.id, "user", question, undefined, undefined, ANALYST_PROMPT_VERSION);
    if (cached?.content) {
      const saved = await saveMessage(thread.id, "assistant", cached.content, undefined, { cached: true }, ANALYST_PROMPT_VERSION);
      return NextResponse.json({ content: cached.content, cached: true, thread_id: thread.id, message_id: saved.id, tool_results: cached.tool_results || [] });
    }

    const messages: AzureChatMessage[] = [
      { role: "system", content: chatSystemPrompt },
      ...prior.slice(-8).map((item: any) => ({ role: item.role === "assistant" ? "assistant" : "user", content: item.content }) as AzureChatMessage),
      { role: "user", content: buildChatPrompt(context, question, activeReport) },
    ];
    const toolResults: Array<{ tool: string; args: Record<string, any>; result: Record<string, any> }> = [];
    let content = "";

    for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
      const data = await runAzureChatCompletion(messages, { tools: AI_TOOLS, maxCompletionTokens: 1100 });
      const message = data.choices?.[0]?.message;
      const calls = message?.tool_calls || [];
      if (!calls.length) {
        content = message?.content || "";
        break;
      }
      messages.push({ role: "assistant", content: message.content || "", tool_calls: calls });
      for (const call of calls) {
        let result: Record<string, any>;
        let args: Record<string, any> = {};
        try {
          args = JSON.parse(call.function.arguments || "{}");
          result = await executeAiTool(call.function.name, args);
        } catch (error) {
          result = { error: error instanceof Error ? error.message : "Tool failed" };
        }
        toolResults.push({ tool: call.function.name, args, result });
        messages.push({ role: "tool", tool_call_id: call.id, content: JSON.stringify(result).slice(0, 6000) });
      }
    }

    if (!content) {
      const data = await runAzureChatCompletion([...messages, { role: "user", content: "Answer now using the available context and tool results. Do not call more tools." }], {
        maxCompletionTokens: 900,
        toolChoice: "none",
      });
      content = data.choices?.[0]?.message?.content || "No answer returned.";
    }

    const saved = await saveMessage(thread.id, "assistant", content, undefined, { tool_results: toolResults }, ANALYST_PROMPT_VERSION);
    await setCache("chat", cacheKey, { content, tool_results: toolResults }, analysis.symbol, taskType, 3600);
    return NextResponse.json({ content, cached: false, thread_id: thread.id, message_id: saved.id, tool_results: toolResults });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "AI chat failed." }, { status: 500 });
  }
}

function validTaskType(value: unknown): AiTaskType {
  return ["stock_report", "resistance_read", "alert_explain", "account_risk", "intraday_plan", "daily_brief", "strategy_compare"].includes(String(value))
    ? (value as AiTaskType)
    : "stock_report";
}

async function ensureThread(symbol: string, taskType: string) {
  const response = await fetch(`${backendUrl}/api/ai/threads?symbol=${encodeURIComponent(symbol)}&task_type=${encodeURIComponent(taskType)}`, { cache: "no-store" });
  const data = await response.json();
  return data.active || data.items?.[0];
}

async function loadMessages(threadId: number) {
  const response = await fetch(`${backendUrl}/api/ai/messages?thread_id=${threadId}&limit=10`, { cache: "no-store" });
  if (!response.ok) return [];
  const data = await response.json();
  return data.items || [];
}

async function saveMessage(threadId: number, role: string, content: string, toolName?: string, payload?: Record<string, any>, promptVersion?: string) {
  const response = await fetch(`${backendUrl}/api/ai/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, role, content, tool_name: toolName, payload, prompt_version: promptVersion }),
  });
  const data = await response.json().catch(() => ({}));
  return data.item || {};
}

async function getCache(kind: string, cacheKey: string) {
  const response = await fetch(`${backendUrl}/api/ai/cache?kind=${encodeURIComponent(kind)}&cache_key=${encodeURIComponent(cacheKey)}`, { cache: "no-store" });
  if (!response.ok) return null;
  const data = await response.json();
  return data.item?.payload || null;
}

async function setCache(kind: string, cacheKey: string, payload: Record<string, any>, symbol: string, taskType: string, ttlSeconds: number) {
  await fetch(`${backendUrl}/api/ai/cache`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, cache_key: cacheKey, payload, symbol, task_type: taskType, ttl_seconds: ttlSeconds }),
  }).catch(() => null);
}

function chatCacheKey(symbol: string, taskType: string, question: string, ctxHash: string) {
  const hourBucket = new Date().toISOString().slice(0, 13);
  return crypto
    .createHash("sha256")
    .update([symbol.toUpperCase(), taskType, normalizeQuestion(question), ctxHash, hourBucket].join(":"))
    .digest("hex");
}

function normalizeQuestion(question: string) {
  return question.trim().toLowerCase().replace(/\s+/g, " ");
}
