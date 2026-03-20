import { NextResponse } from "next/server";

const API_BASE =
  process.env.TUMINH_API_BASE ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://127.0.0.1:8000";

export async function GET() {
  try {
    const url = `${API_BASE.replace(/\/$/, "")}/api/knowledge/stats`;
    const res = await fetch(url, { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json(
      { total_contributions: 0, verified_entries: 0, regions_covered: 0, last_updated: null },
      { status: 502 }
    );
  }
}
