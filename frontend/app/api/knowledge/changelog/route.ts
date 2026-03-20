import { NextRequest, NextResponse } from "next/server";

const API_BASE =
  process.env.TUMINH_API_BASE ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const limit = searchParams.get("limit") || "20";
    const url = `${API_BASE.replace(/\/$/, "")}/api/knowledge/changelog?limit=${limit}`;
    const res = await fetch(url, { cache: "no-store" });
    const data = await res.json().catch(() => []);
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json([], { status: 502 });
  }
}
