import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q") || "";
  const limit = request.nextUrl.searchParams.get("limit") || "12";
  if (query.trim().length < 2) {
    return NextResponse.json({ items: [], count: 0 });
  }
  try {
    const response = await fetch(`${backendUrl}/api/instruments?search=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`, {
      cache: "no-store",
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { items: [], count: 0, error: error instanceof Error ? error.message : "Instrument search failed." },
      { status: 200 },
    );
  }
}
