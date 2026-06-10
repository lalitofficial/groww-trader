export type AzureChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_call_id?: string;
  tool_calls?: Array<{
    id: string;
    type: "function";
    function: { name: string; arguments: string };
  }>;
};

export type AzureTool = {
  type: "function";
  function: {
    name: string;
    description?: string;
    parameters: Record<string, any>;
  };
};

export async function runAzureTeacher(prompt: string, systemPrompt: string, options: { maxCompletionTokens?: number } = {}) {
  const data = await runAzureChatCompletion(
    [
      { role: "system", content: systemPrompt },
      { role: "user", content: prompt },
    ],
    { maxCompletionTokens: options.maxCompletionTokens ?? 1200 },
  );
  const content = data.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("Azure OpenAI returned an empty analyst response.");
  }
  return content as string;
}

export async function runAzureChatCompletion(
  messages: AzureChatMessage[],
  options: { maxCompletionTokens?: number; tools?: AzureTool[]; toolChoice?: "auto" | "none" } = {},
) {
  const endpoint = process.env.AZURE_OPENAI_ENDPOINT?.replace(/\/+$/, "");
  const deployment = process.env.AZURE_OPENAI_DEPLOYMENT;
  const apiVersion = process.env.AZURE_OPENAI_API_VERSION || "2024-12-01-preview";

  if (!endpoint || !deployment || !process.env.AZURE_OPENAI_API_KEY) {
    throw new Error("Missing Azure OpenAI configuration.");
  }

  const response = await fetch(
    `${endpoint}/openai/deployments/${encodeURIComponent(deployment)}/chat/completions?api-version=${apiVersion}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "api-key": process.env.AZURE_OPENAI_API_KEY,
      },
      body: JSON.stringify({
        messages,
        tools: options.tools,
        tool_choice: options.tools?.length ? options.toolChoice ?? "auto" : undefined,
        max_completion_tokens: options.maxCompletionTokens ?? 1200,
      }),
    },
  );

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || `Azure OpenAI request failed with ${response.status}`);
  }
  await recordAzureUsage(data?.usage);
  return data;
}

export async function streamAzureChatCompletion(
  messages: AzureChatMessage[],
  options: { maxCompletionTokens?: number; tools?: AzureTool[]; toolChoice?: "auto" | "none" } = {},
) {
  const endpoint = process.env.AZURE_OPENAI_ENDPOINT?.replace(/\/+$/, "");
  const deployment = process.env.AZURE_OPENAI_DEPLOYMENT;
  const apiVersion = process.env.AZURE_OPENAI_API_VERSION || "2024-12-01-preview";

  if (!endpoint || !deployment || !process.env.AZURE_OPENAI_API_KEY) {
    throw new Error("Missing Azure OpenAI configuration.");
  }

  const response = await fetch(
    `${endpoint}/openai/deployments/${encodeURIComponent(deployment)}/chat/completions?api-version=${apiVersion}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "api-key": process.env.AZURE_OPENAI_API_KEY,
      },
      body: JSON.stringify({
        messages,
        tools: options.tools,
        tool_choice: options.tools?.length ? options.toolChoice ?? "auto" : undefined,
        max_completion_tokens: options.maxCompletionTokens ?? 1200,
        stream: true,
        stream_options: { include_usage: true },
      }),
    },
  );

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data?.error?.message || `Azure OpenAI request failed with ${response.status}`);
  }
  return response;
}

async function recordAzureUsage(usage?: { prompt_tokens?: number; completion_tokens?: number }) {
  if (!usage) return;
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
  try {
    await fetch(`${backendUrl}/api/ai/budget`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "azure_openai",
        prompt_tokens: usage.prompt_tokens || 0,
        completion_tokens: usage.completion_tokens || 0,
      }),
    });
  } catch {
    // Budget tracking must never fail the analyst response.
  }
}
