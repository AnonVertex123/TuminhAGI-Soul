"use client";

import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Pin } from "lucide-react";

type SpaceItem = { id: string; label: string };
type ChannelItem = { id: string; label: string };
type NavSectionId = "home" | "inbox" | "assigned" | "my_tasks" | "more";

export default function SidebarTree() {
  const [favoritesOpen, setFavoritesOpen] = useState(true);

  const navItems: { id: NavSectionId; label: string }[] = useMemo(
    () => [
      { id: "home", label: "Home" },
      { id: "inbox", label: "Inbox" },
      { id: "assigned", label: "Assigned" },
      { id: "my_tasks", label: "My Tasks" },
      { id: "more", label: "More" },
    ],
    []
  );

  const spaces: SpaceItem[] = useMemo(
    () => [
      { id: "space-today", label: "Chẩn đoán hôm nay" },
      { id: "space-history", label: "Lịch sử bệnh nhân" },
      { id: "space-protocol", label: "Phác đồ điều trị" },
      { id: "space-herbs", label: "Thuốc Nam Encyclopedia" },
    ],
    []
  );

  const channels: ChannelItem[] = useMemo(
    () => [
      { id: "ch-new", label: "Cập nhật mới" },
      { id: "ch-daily", label: "Báo cáo hàng ngày" },
    ],
    []
  );

  const recentSessions = useMemo(
    () => [
      { id: "s1", name: "Ca khám #001", urgency: "routine" as const, track: "herbal", done: 0, total: 3 },
      { id: "s2", name: "Ca khám #002", urgency: "urgent" as const, track: "both", done: 0, total: 5 },
      { id: "s3", name: "Ca khám #003", urgency: "routine" as const, track: "herbal", done: 1, total: 3 },
    ],
    []
  );

  return (
    <aside className="w-[220px] shrink-0 bg-[#FFFFFF] border-r border-[#E8E8F0] h-full overflow-hidden flex flex-col">
      <div className="p-3 border-b border-[#E8E8F0] flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-[#1B1B2F] flex items-center gap-2">
            <span aria-hidden>🌿</span>
            <span className="truncate">Tự Minh's Workspace</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[#6B6B8A]">
          <Pin className="w-[16px] h-[16px]" />
          <ChevronDown className="w-[16px] h-[16px]" />
        </div>
      </div>

      <div className="p-3 overflow-y-auto space-y-4">
        <div>
          <button
            type="button"
            className="w-full h-[30px] rounded-full bg-[#7B68EE] text-white text-[12px] font-semibold hover:opacity-95 transition-opacity"
          >
            + Tạo mới
          </button>
        </div>

        <div className="space-y-2">
          {navItems.map((it, idx) => (
            <div
              key={it.id}
              className={[
                "text-[12px] px-2 py-1 rounded-lg cursor-pointer select-none",
                idx === 0 ? "bg-[#EEF0FF] text-[#7B68EE]" : "hover:bg-[#F0F0F8] text-[#1B1B2F]",
              ].join(" ")}
            >
              {it.label}
            </div>
          ))}
        </div>

        <div>
          <button
            type="button"
            onClick={() => setFavoritesOpen((v) => !v)}
            className="w-full flex items-center justify-between text-[12px] text-[#6B6B8A] hover:text-[#1B1B2F]"
          >
            <span>Favorites section (collapsible)</span>
            {favoritesOpen ? <ChevronDown className="w-[16px] h-[16px]" /> : <ChevronRight className="w-[16px] h-[16px]" />}
          </button>
          {favoritesOpen ? (
            <div className="mt-2 space-y-1">
              <div className="text-[12px] px-2 py-1 rounded hover:bg-[#F0F0F8] text-[#1B1B2F]">Click to add favorites...</div>
            </div>
          ) : null}
        </div>

        <div>
          <div className="text-[12px] font-semibold text-[#1B1B2F] flex items-center gap-2">
            <span aria-hidden>▼</span> Bệnh nhân Space
          </div>
          <div className="mt-2 space-y-1">
            {spaces.map((s) => (
              <div key={s.id} className="text-[12px] px-2 py-1 rounded hover:bg-[#F0F0F8] text-[#1B1B2F] flex items-center gap-2">
                <span aria-hidden>📁</span>
                <span className="truncate">{s.label}</span>
              </div>
            ))}
            <button
              type="button"
              className="text-[12px] px-2 py-1 rounded hover:bg-[#F0F0F8] text-[#7B68EE] w-full text-left"
            >
              + New Space
            </button>
          </div>
        </div>

        <div>
          <div className="text-[12px] font-semibold text-[#1B1B2F] flex items-center gap-2">
            <span aria-hidden>#</span> Channels
          </div>
          <div className="mt-2 space-y-1">
            {channels.map((c) => (
              <div key={c.id} className="text-[12px] px-2 py-1 rounded hover:bg-[#F0F0F8] text-[#1B1B2F]">
                # {c.label}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[12px] font-semibold text-[#1B1B2F] flex items-center gap-2">
            <span aria-hidden>☰</span> Lists (recent sessions)
          </div>
          <div className="mt-2 space-y-2">
            {recentSessions.map((s) => {
              const badge =
                s.urgency === "urgent"
                  ? { bg: "bg-amber-100", text: "text-amber-800" }
                  : { bg: "bg-emerald-100", text: "text-emerald-800" };

              const pct = Math.round((s.done / s.total) * 100);

              return (
                <div key={s.id} className="rounded-xl bg-[#FFFFFF] ring-1 ring-black/5 p-2 hover:bg-[#F0F0F8] transition-colors">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[12px] font-semibold truncate">{s.name}</div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${badge.bg} ${badge.text}`}>{s.urgency}</span>
                  </div>
                  <div className="mt-1 text-[11px] text-[#6B6B8A] flex justify-between">
                    <span className="truncate">Track: {s.track}</span>
                    <span className="font-mono">{s.done}/{s.total}</span>
                  </div>
                  <div className="mt-2 h-[6px] rounded-full bg-[#E8E8F0] overflow-hidden">
                    <div className="h-full bg-[#7B68EE]" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}

