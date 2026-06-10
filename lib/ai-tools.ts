import crypto from "crypto";
import type { AzureTool } from "@/lib/ai";
import type { Timeframe } from "@/lib/types";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const TOOL_TTL_SECONDS = 15 * 60;

export const AI_TOOLS: AzureTool[] = [
  tool("get_quote", "Fetch the latest public quote for a symbol.", { symbol: stringParam("NSE symbol") }),
  tool("get_fundamentals", "Fetch Screener fundamentals for a symbol.", { symbol: stringParam("NSE symbol") }),
  tool("get_option_chain", "Fetch NSE option-chain summary and strikes for a symbol.", { symbol: stringParam("NSE symbol") }),
  tool("get_announcements", "Fetch recent corporate announcements, optionally for a symbol.", { symbol: optionalStringParam("NSE symbol") }),
  tool("get_breadth", "Fetch market breadth snapshots.", {}),
  tool("get_fii_dii", "Fetch recent FII/DII data.", {}),
  tool("run_strategy", "Run one StrategyLab strategy on a symbol/timeframe.", {
    id: stringParam("Strategy id"),
    symbol: stringParam("NSE symbol"),
    timeframe: optionalStringParam("5m, 15m, 30m, hourly, or daily"),
  }),
  tool("bench_strategies", "Benchmark strategies for a symbol/timeframe.", {
    symbol: stringParam("NSE symbol"),
    timeframe: optionalStringParam("5m, 15m, 30m, hourly, or daily"),
  }),
];

export async function executeAiTool(name: string, rawArgs: Record<string, any>) {
  const args = sanitizeArgs(name, rawArgs || {});
  const cacheKey = toolCacheKey(name, args);
  const cached = await getToolCache(cacheKey);
  if (cached) return { ...cached, cached: true };

  const payload = await callTool(name, args);
  await setToolCache(cacheKey, name, args, payload);
  return { ...payload, cached: false };
}

function tool(name: string, description: string, properties: Record<string, any>): AzureTool {
  const required = Object.entries(properties)
    .filter(([, value]) => !value.optional)
    .map(([key]) => key);
  return {
    type: "function",
    function: {
      name,
      description,
      parameters: {
        type: "object",
        additionalProperties: false,
        properties: Object.fromEntries(Object.entries(properties).map(([key, value]) => [key, value.schema || value])),
        required,
      },
    },
  };
}

function stringParam(description: string) {
  return { schema: { type: "string", description } };
}

function optionalStringParam(description: string) {
  return { optional: true, schema: { type: "string", description } };
}

function sanitizeArgs(name: string, args: Record<string, any>) {
  if (name === "get_breadth" || name === "get_fii_dii") return {};
  const symbol = typeof args.symbol === "string" ? args.symbol.trim().toUpperCase() : "";
  if (["get_quote", "get_fundamentals", "get_option_chain"].includes(name) && !symbol) throw new Error(`${name} requires symbol.`);
  if (name === "get_announcements") return symbol ? { symbol } : {};
  if (name === "run_strategy") {
    const id = typeof args.id === "string" ? args.id.trim() : "";
    if (!id || !symbol) throw new Error("run_strategy requires id and symbol.");
    return { id, symbol, timeframe: normalizeTimeframe(args.timeframe) };
  }
  if (name === "bench_strategies") {
    if (!symbol) throw new Error("bench_strategies requires symbol.");
    return { symbol, timeframe: normalizeTimeframe(args.timeframe) };
  }
  return { symbol };
}

async function callTool(name: string, args: Record<string, any>) {
  if (name === "get_quote") return fetchJson(`${backendUrl}/api/sources/quote/${encodeURIComponent(args.symbol)}`);
  if (name === "get_fundamentals") return fetchJson(`${backendUrl}/api/sources/fundamentals/${encodeURIComponent(args.symbol)}`);
  if (name === "get_option_chain") return fetchJson(`${backendUrl}/api/sources/option-chain/${encodeURIComponent(args.symbol)}`);
  if (name === "get_announcements") {
    const query = args.symbol ? `?symbol=${encodeURIComponent(args.symbol)}` : "";
    return fetchJson(`${backendUrl}/api/sources/announcements${query}`);
  }
  if (name === "get_breadth") return fetchJson(`${backendUrl}/api/sources/breadth`);
  if (name === "get_fii_dii") return fetchJson(`${backendUrl}/api/sources/fii-dii`);
  if (name === "run_strategy") {
    return fetchJson(`${backendUrl}/api/strategies/${encodeURIComponent(args.id)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: args.symbol, timeframe: args.timeframe }),
    });
  }
  if (name === "bench_strategies") {
    return fetchJson(`${backendUrl}/api/strategies/bench`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: args.symbol, timeframe: args.timeframe }),
    });
  }
  throw new Error(`Unknown AI tool: ${name}`);
}

function normalizeTimeframe(value: unknown): Timeframe {
  return value === "5m" || value === "15m" || value === "30m" || value === "hourly" || value === "daily" ? value : "daily";
}

async function getToolCache(cacheKey: string) {
  try {
    const data = await fetchJson<{ item: { payload: Record<string, any> } }>(`${backendUrl}/api/ai/tool-cache?cache_key=${encodeURIComponent(cacheKey)}`);
    return data.item.payload;
  } catch {
    return null;
  }
}

async function setToolCache(cacheKey: string, toolName: string, args: Record<string, any>, payload: Record<string, any>) {
  try {
    await fetchJson(`${backendUrl}/api/ai/tool-cache`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cache_key: cacheKey, tool_name: toolName, args, payload, ttl_seconds: TOOL_TTL_SECONDS }),
    });
  } catch {
    // Tool cache is an optimization only.
  }
}

function toolCacheKey(name: string, args: Record<string, any>) {
  return crypto.createHash("sha256").update(`${name}:${stableStringify(args)}`).digest("hex");
}

function stableStringify(value: any): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function fetchJson<T = any>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || data?.error || `${response.status} ${response.statusText}`);
  return data as T;
}
