import { NextRequest, NextResponse } from "next/server";
import type { Hospital } from "@/lib/emergency";
import { estimateDriveMinutes, haversineKm } from "@/lib/emergency";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type OverpassElement = {
  type: string;
  id: number;
  lat?: number;
  lon?: number;
  center?: { lat: number; lon: number };
  tags?: Record<string, string>;
};

type GooglePlace = {
  place_id: string;
  name: string;
  vicinity?: string;
  formatted_address?: string;
  geometry?: { location: { lat: number; lng: number } };
  rating?: number;
  opening_hours?: { open_now?: boolean };
  international_phone_number?: string;
};

function hospitalFromGoogle(p: GooglePlace, originLat: number, originLng: number): Hospital {
  const loc = p.geometry?.location;
  const lat = loc?.lat ?? originLat;
  const lng = loc?.lng ?? originLng;
  const d = haversineKm(originLat, originLng, lat, lng);
  return {
    id: `g:${p.place_id}`,
    name: p.name,
    address: p.formatted_address || p.vicinity || "",
    phone: p.international_phone_number,
    distance_km: Math.round(d * 10) / 10,
    duration_drive_min: estimateDriveMinutes(d),
    lat,
    lng,
    is_open_now: p.opening_hours?.open_now ?? true,
    emergency_available: true,
    rating: p.rating,
  };
}

async function fetchGoogleNearby(
  lat: number,
  lng: number,
  apiKey: string
): Promise<Hospital[] | null> {
  const types = ["hospital", "doctor"];
  const seen = new Set<string>();
  const all: Hospital[] = [];

  for (const t of types) {
    const url = new URL("https://maps.googleapis.com/maps/api/place/nearbysearch/json");
    url.searchParams.set("location", `${lat},${lng}`);
    url.searchParams.set("radius", "5000");
    url.searchParams.set("type", t);
    url.searchParams.set("keyword", "emergency hospital bệnh viện cấp cứu");
    url.searchParams.set("key", apiKey);
    const res = await fetch(url.toString(), { cache: "no-store" });
    if (!res.ok) continue;
    const j = (await res.json()) as { results?: GooglePlace[]; status: string };
    if (j.status !== "OK" && j.status !== "ZERO_RESULTS") continue;
    for (const p of j.results || []) {
      if (seen.has(p.place_id)) continue;
      seen.add(p.place_id);
      all.push(hospitalFromGoogle(p, lat, lng));
    }
  }

  if (all.length === 0) return null;
  all.sort((a, b) => a.distance_km - b.distance_km);
  return all.slice(0, 5);
}

function hospitalFromOverpass(
  el: OverpassElement,
  originLat: number,
  originLng: number
): Hospital | null {
  const lat = el.lat ?? el.center?.lat;
  const lng = el.lon ?? el.center?.lon;
  if (lat == null || lng == null) return null;
  const tags = el.tags || {};
  const name =
    tags.name || tags["name:en"] || tags["name:vi"] || "Bệnh viện / Trạm y tế";
  const addr = [tags["addr:street"], tags["addr:city"], tags["addr:district"]]
    .filter(Boolean)
    .join(", ");
  const d = haversineKm(originLat, originLng, lat, lng);
  return {
    id: `o:${el.type}:${el.id}`,
    name,
    address: addr || tags["addr:full"] || "",
    phone: tags.phone || tags["contact:phone"],
    distance_km: Math.round(d * 10) / 10,
    duration_drive_min: estimateDriveMinutes(d),
    lat,
    lng,
    is_open_now: true,
    emergency_available: tags.emergency === "yes" || tags.amenity === "hospital",
  };
}

async function fetchOverpass(lat: number, lng: number): Promise<Hospital[]> {
  const query = `
[out:json][timeout:25];
(
  node["amenity"="hospital"](around:5000,${lat},${lng});
  way["amenity"="hospital"](around:5000,${lat},${lng});
  node["amenity"="clinic"](around:3000,${lat},${lng});
  way["amenity"="clinic"](around:3000,${lat},${lng});
);
out center;
`;
  const res = await fetch("https://overpass-api.de/api/interpreter", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `data=${encodeURIComponent(query)}`,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Overpass ${res.status}`);
  const j = (await res.json()) as { elements?: OverpassElement[] };
  const list: Hospital[] = [];
  const seen = new Set<string>();
  for (const el of j.elements || []) {
    const h = hospitalFromOverpass(el, lat, lng);
    if (!h) continue;
    const key = `${h.lat.toFixed(5)},${h.lng.toFixed(5)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    list.push(h);
  }
  list.sort((a, b) => a.distance_km - b.distance_km);
  return list.slice(0, 5);
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { lat?: number; lng?: number };
    const lat = Number(body.lat);
    const lng = Number(body.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return NextResponse.json({ error: "Invalid lat/lng" }, { status: 400 });
    }

    const apiKey =
      process.env.GOOGLE_MAPS_API_KEY ||
      process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY ||
      "";

    if (apiKey) {
      const google = await fetchGoogleNearby(lat, lng, apiKey);
      if (google && google.length > 0) {
        return NextResponse.json({ hospitals: google, source: "google" });
      }
    }

    const hospitals = await fetchOverpass(lat, lng);
    return NextResponse.json({ hospitals, source: "overpass" });
  } catch (e) {
    console.error("[emergency/hospitals]", e);
    return NextResponse.json(
      { error: String(e), hospitals: [] as Hospital[] },
      { status: 500 }
    );
  }
}
