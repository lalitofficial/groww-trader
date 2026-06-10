import { describe, expect, it, vi } from "vitest";
import { runAzureTeacher } from "./ai";

describe("runAzureTeacher", () => {
  it("throws when Azure env is missing", async () => {
    await expect(runAzureTeacher("hello", "system")).rejects.toThrow("Missing Azure OpenAI configuration");
  });

  it("returns message content from Azure response", async () => {
    vi.stubEnv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com");
    vi.stubEnv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4");
    vi.stubEnv("AZURE_OPENAI_API_KEY", "key");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ choices: [{ message: { content: "report" } }] }),
      })),
    );

    await expect(runAzureTeacher("hello", "system")).resolves.toBe("report");
  });
});
