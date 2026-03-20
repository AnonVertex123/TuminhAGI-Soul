"use client";

import React, { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { Hospital, UserLocation } from "@/lib/emergency";
import {
  resolveUserLocation,
  fetchNearbyHospitals,
  getHotlinesForCountry,
  resolveCountryCodeFromGeo,
  openDirections,
  shareEmergencyLocation,
  openWhatsAppShare,
  openZaloShare,
  buildShareMessage,
  loadCachedHospitals,
  loadCachedUserLocation,
  OFFLINE_VN_INSTRUCTIONS,
  parseManualAddressToLocation,
} from "@/lib/emergency";

const EmergencyMap = dynamic(() => import("@/components/EmergencyMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[300px] rounded-xl bg-red-50 flex items-center justify-center text-sm text-red-800">
      <span className="inline-flex items-center gap-2">
        <span className="h-5 w-5 border-2 border-red-600 border-t-transparent rounded-full animate-spin" />
        Đang tải bản đồ…
      </span>
    </div>
  ),
});

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8 text-red-900">
      <span className="h-10 w-10 border-[3px] border-red-600 border-t-transparent rounded-full animate-spin" />
      <p className="text-[12px] font-semibold text-center px-2">{label}</p>
    </div>
  );
}

export default function EmergencyResponsePanel({
  emergencyReason,
  diagnosisSummary,
  className = "",
}: {
  emergencyReason?: string;
  /** Top candidates / API text — không gồm thuốc Nam */
  diagnosisSummary?: string | null;
  className?: string;
}) {
  const [loc, setLoc] = useState<UserLocation | null>(() =>
    typeof window !== "undefined" ? loadCachedUserLocation() : null
  );
  const [resolvingLoc, setResolvingLoc] = useState(true);
  const [loadingHospitals, setLoadingHospitals] = useState(false);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [needsManual, setNeedsManual] = useState(false);
  const [manualInput, setManualInput] = useState("");
  const [cachedNotice, setCachedNotice] = useState(false);
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  const countryCode = resolveCountryCodeFromGeo(loc?.country, loc?.countryCode);
  const hotlines = getHotlinesForCountry(countryCode);

  useEffect(() => {
    const up = () => setOnline(navigator.onLine);
    window.addEventListener("online", up);
    window.addEventListener("offline", up);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", up);
    };
  }, []);

  const loadHospitals = useCallback(async (u: UserLocation) => {
    if (!online) {
      const c = loadCachedHospitals();
      if (c?.hospitals?.length) {
        setHospitals(c.hospitals);
        setCachedNotice(true);
      }
      return;
    }
    setLoadingHospitals(true);
    try {
      const list = await fetchNearbyHospitals(u.lat, u.lng);
      setHospitals(list);
      setCachedNotice(false);
    } catch {
      const c = loadCachedHospitals();
      if (c?.hospitals?.length) {
        setHospitals(c.hospitals);
        setCachedNotice(true);
      }
    } finally {
      setLoadingHospitals(false);
    }
  }, [online]);

  /** Mount only: GPS → silent IP; giữ cache nếu cả hai lỗi */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setResolvingLoc(true);
      setNeedsManual(false);
      const { location } = await resolveUserLocation();
      if (cancelled) return;
      setResolvingLoc(false);
      if (location) {
        setLoc(location);
        setNeedsManual(false);
        return;
      }
      const cached = loadCachedUserLocation();
      if (cached) {
        setLoc(cached);
        setNeedsManual(false);
        return;
      }
      setNeedsManual(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Có tọa độ (cache ngay hoặc sau GPS/IP) → fetch BV */
  useEffect(() => {
    if (!loc) return;
    void loadHospitals(loc);
  }, [loc, loadHospitals]);

  const applyManualCoords = () => {
    const parts = manualInput.split(/[,\s]+/).map(Number).filter(Number.isFinite);
    if (parts.length >= 2) {
      const [lat, lng] = parts;
      if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
        const u = parseManualAddressToLocation(lat, lng, manualInput);
        setLoc(u);
        setNeedsManual(false);
        void loadHospitals(u);
      }
    }
  };

  const shareText = loc ? buildShareMessage(loc, hospitals[0]) : "";
  const showMapSlot = Boolean(loc && !needsManual);
  const showLocSpinner = resolvingLoc && !loc;

  return (
    <div
      className={`flex flex-col h-full min-h-0 bg-[#FFF5F5] border-l-2 border-red-600 shadow-[0_0_0_2px_rgba(220,38,38,0.25)] ${className}`}
      style={{
        animation: "tuminh-emergency-pulse 2s ease-in-out infinite",
      }}
    >
      <style>{`
        @keyframes tuminh-emergency-pulse {
          0%, 100% { box-shadow: 0 0 0 2px rgba(220,38,38,0.35); }
          50% { box-shadow: 0 0 0 4px rgba(220,38,38,0.55); }
        }
      `}</style>

      <div className="shrink-0 px-3 py-2 border-b-2 border-red-600 bg-red-600 text-white">
        <div className="text-[11px] font-black tracking-wide">🚨 TÌNH TRẠNG KHẨN CẤP</div>
        {emergencyReason ? (
          <p className="text-[11px] mt-1 opacity-95 leading-snug">{emergencyReason}</p>
        ) : null}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        {diagnosisSummary ? (
          <div className="rounded-xl bg-white/95 ring-1 ring-red-200 p-3 text-[11px] text-[#1B1B2F] whitespace-pre-wrap leading-relaxed">
            <div className="font-bold text-red-800 mb-1">Phân tích nhanh (không gợi ý thuốc Nam)</div>
            {diagnosisSummary}
          </div>
        ) : null}

        {!online && (
          <div className="rounded-lg bg-amber-100 border border-amber-400 px-3 py-2 text-[11px] text-amber-950">
            <strong>Mất mạng.</strong> {OFFLINE_VN_INSTRUCTIONS}
            {cachedNotice && (
              <p className="mt-2 font-semibold">Dữ liệu bệnh viện từ lần truy cập trước (có thể cũ).</p>
            )}
          </div>
        )}

        <div className="rounded-xl bg-white ring-2 ring-red-200 p-3">
          <div className="text-[11px] font-bold text-red-900 mb-2">📞 GỌI NGAY</div>
          <div className="flex flex-wrap gap-2">
            <a
              href={`tel:${hotlines.ambulance}`}
              className="inline-flex items-center justify-center min-h-[44px] px-4 rounded-xl bg-red-600 text-white font-extrabold text-base shadow-lg active:scale-[0.98]"
            >
              🚑 {hotlines.ambulance}
            </a>
            <a
              href={`tel:${hotlines.police}`}
              className="inline-flex items-center justify-center min-h-[40px] px-3 rounded-lg bg-slate-800 text-white text-sm font-semibold"
            >
              👮 {hotlines.police}
            </a>
            <a
              href={`tel:${hotlines.fire}`}
              className="inline-flex items-center justify-center min-h-[40px] px-3 rounded-lg bg-orange-600 text-white text-sm font-semibold"
            >
              🔥 {hotlines.fire}
            </a>
          </div>
          <p className="text-[10px] text-slate-600 mt-2">Nhấn để gọi (điện thoại)</p>
        </div>

        <div className="rounded-xl bg-white ring-1 ring-red-100 p-3 min-h-[120px]">
          <div className="text-[11px] font-bold text-[#1B1B2F] mb-2">🏥 Bệnh viện gần nhất</div>

          {loc && !needsManual && (
            <p className="text-[10px] text-slate-500 mb-2">
              Vị trí: {loc.source === "gps" ? "GPS" : loc.source === "ip" ? "Ước tính theo IP (im lặng)" : "Thủ công"}
              {loc.city ? ` · ${loc.city}` : ""}
              {resolvingLoc ? " — đang làm mới…" : ""}
            </p>
          )}

          {showLocSpinner && <Spinner label="Đang lấy vị trí (GPS hoặc IP)…" />}

          {needsManual && !loc && (
            <div className="space-y-2">
              <p className="text-[11px] text-red-800">
                Không lấy được GPS và vị trí IP. Nhập tọa độ (cuối cùng).
              </p>
              <label className="block text-[10px] font-semibold text-slate-600">
                Vĩ độ, kinh độ — ví dụ HCM: 10.776, 106.700
              </label>
              <input
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                placeholder="10.776, 106.700"
                className="w-full rounded-lg border border-slate-300 px-2 py-2 text-sm"
              />
              <button
                type="button"
                onClick={applyManualCoords}
                className="w-full py-2 rounded-lg bg-red-600 text-white text-sm font-bold"
              >
                Áp dụng vị trí
              </button>
            </div>
          )}

          {showMapSlot && loc && (
            <>
              {loadingHospitals && (
                <div className="flex items-center gap-2 text-[12px] text-slate-600 mb-2">
                  <span className="h-4 w-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin shrink-0" />
                  Đang tìm bệnh viện (OSM)…
                </div>
              )}
              <EmergencyMap user={loc} hospitals={hospitals} routeToFirst={hospitals.length > 0} />
              <ul className="mt-3 space-y-3">
                {hospitals.slice(0, 5).map((h, i) => (
                  <li
                    key={h.id}
                    className="rounded-lg border border-slate-200 bg-slate-50/80 p-2 text-[11px]"
                  >
                    <div className="font-bold text-[#1B1B2F]">
                      {i + 1}. {h.name}
                    </div>
                    <div className="text-slate-600 mt-0.5">
                      📍 {h.distance_km} km — 🚗 ~{h.duration_drive_min} phút
                    </div>
                    {h.address ? <div className="text-slate-500">{h.address}</div> : null}
                    {h.phone ? (
                      <div>
                        <a href={`tel:${h.phone.replace(/\s/g, "")}`} className="text-blue-700 font-semibold">
                          📞 {h.phone}
                        </a>
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2 mt-2">
                      <button
                        type="button"
                        onClick={() => openDirections(loc, h)}
                        className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-[11px] font-bold"
                      >
                        🗺️ Chỉ đường
                      </button>
                      {h.phone ? (
                        <a
                          href={`tel:${h.phone.replace(/\s/g, "")}`}
                          className="inline-flex items-center px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[11px] font-bold"
                        >
                          📞 Gọi ngay
                        </a>
                      ) : null}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {h.is_open_now ? "✅ Đang mở (ước tính)" : "⏳ Giờ mở chưa rõ"} —{" "}
                      {h.emergency_available ? "Có cấp cứu / BV (OSM)" : "CSYT"}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {loc && (
          <div className="rounded-xl bg-white ring-1 ring-slate-200 p-3 space-y-2">
            <div className="text-[11px] font-bold">📤 Chia sẻ vị trí</div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void shareEmergencyLocation(loc, hospitals[0])}
                className="px-3 py-1.5 rounded-lg bg-violet-600 text-white text-[11px] font-semibold"
              >
                Chia sẻ / Sao chép
              </button>
              <button
                type="button"
                onClick={() => openWhatsAppShare(shareText)}
                className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-[11px] font-semibold"
              >
                WhatsApp
              </button>
              <button
                type="button"
                onClick={() => openZaloShare(shareText)}
                className="px-3 py-1.5 rounded-lg bg-blue-500 text-white text-[11px] font-semibold"
              >
                Zalo
              </button>
            </div>
          </div>
        )}

        <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-[11px] text-red-900 font-semibold">
          ⚠️ Không tự dùng bất kỳ thuốc nào trước khi được bác sĩ hướng dẫn.
        </div>
      </div>
    </div>
  );
}
