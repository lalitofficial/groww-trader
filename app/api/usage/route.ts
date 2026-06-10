import { NextResponse } from "next/server";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${backendUrl}/api/usage`, { cache: "no-store" });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { total_requests: 0, error_requests: 0, recent_5m: 0, uptime_seconds: 0, last_status: null, last_path: null, avg_duration_ms_5m: 0, error: error instanceof Error ? error.message : "Usage unavailable" },
      { status: 200 },
    );
  }
}
