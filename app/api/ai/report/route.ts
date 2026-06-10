import { NextRequest, NextResponse } from "next/server";
import { runAzureTeacher } from "@/lib/ai";
import { buildTaskContext, buildTaskPrompt, contextHash, contextSummary, reportSystemPrompt, type AiTaskType } from "@/lib/ai-context";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  try {
    const symbol = request.nextUrl.searchParams.get("symbol");
    const limit = request.nextUrl.searchParams.get("limit") || "8";
    const taskType = request.nextUrl.searchParams.get("task_type") || "stock_report";
    if (!symbol) {
      return NextResponse.json({ error: "Missing symbol." }, { status: 400 });
    }
    const response = await fetch(
      `${backendUrl}/api/ai/reports?symbol=${encodeURIComponent(symbol)}&limit=${encodeURIComponent(limit)}&task_type=${encodeURIComponent(taskType)}`,
      { cache: "no-store" },
    );
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Report history failed." }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const { analysis, force = false, task_type = "stock_report" } = await request.json();
    const taskType = normalizeTaskType(task_type);
    const context = buildTaskContext(analysis, taskType);
    const hash = contextHash(context);
    if (!force) {
      const cached = await findCachedReport(analysis.symbol, hash, taskType);
      if (cached) {
        return NextResponse.json({ content: cached.content, item: cached, cached: true, context_hash: hash });
      }
    }
    const content = await runAzureTeacher(buildTaskPrompt(context, taskType), reportSystemPrompt, { maxCompletionTokens: 1800 });
    await fetch(`${backendUrl}/api/ai/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: analysis.symbol,
        task_type: taskType,
        company: analysis.company,
        content,
        model: process.env.AZURE_OPENAI_DEPLOYMENT || "azure-openai",
        prompt_version: context.prompt_version,
        context_hash: hash,
        context_summary: contextSummary(context),
      }),
    }).catch(() => null);
    return NextResponse.json({ content, cached: false, context_hash: hash, task_type: taskType });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "AI report failed." }, { status: 500 });
  }
}

async function findCachedReport(symbol: string, hash: string, taskType: AiTaskType) {
  const response = await fetch(
    `${backendUrl}/api/ai/reports?symbol=${encodeURIComponent(symbol)}&limit=12&task_type=${encodeURIComponent(taskType)}`,
    { cache: "no-store" },
  );
  if (!response.ok) return null;
  const data = await response.json();
  return (data.items || []).find((item: any) => item.context_hash === hash) || null;
}

function normalizeTaskType(value: string): AiTaskType {
  return ["stock_report", "resistance_read", "alert_explain", "account_risk", "intraday_plan", "daily_brief", "strategy_compare"].includes(value)
    ? (value as AiTaskType)
    : "stock_report";
}
