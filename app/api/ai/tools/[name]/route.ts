import { NextResponse } from "next/server";
import { executeAiTool } from "@/lib/ai-tools";

export async function POST(request: Request, { params }: { params: Promise<{ name: string }> }) {
  try {
    const { name } = await params;
    const body = await request.json().catch(() => ({}));
    const result = await executeAiTool(name, body.args || body || {});
    return NextResponse.json({ result });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Tool execution failed." }, { status: 500 });
  }
}
