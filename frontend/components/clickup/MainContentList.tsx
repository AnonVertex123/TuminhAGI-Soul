"use client";

import React, { useState } from "react";
import { LayoutList, Plus } from "lucide-react";

type Urgency = "routine" | "urgent" | "emergency";
type Status = "todo" | "in_progress";

type Session = {
  id: string;
  name: string;
  symptoms: string;
  urgency: Urgency;
  status: Status;
  assignee?: string;
  due?: string;
  priority?: number;
};

const SESSIONS: Session[] = [
  { id: "1", name: "Ca khám #001", symptoms: "Đau ngực", urgency: "routine", status: "todo" },
  { id: "2", name: "Ca khám #002", symptoms: "Sốt cao", urgency: "urgent", status: "todo" },
  { id: "3", name: "Ca khám #003", symptoms: "Trễ kinh", urgency: "routine", status: "todo" },
  { id: "4", name: "Ca khám #004", symptoms: "Đang chẩn đoán", urgency: "urgent", status: "in_progress" },
];

function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  const styles: Record<Urgency, { bg: string; text: string; pulse?: boolean }> = {
    routine: { bg: "bg-emerald-100", text: "text-emerald-800" },
    urgent: { bg: "bg-amber-100", text: "text-amber-800" },
    emergency: { bg: "bg-red-100", text: "text-red-800", pulse: true },
  };
  const s = styles[urgency];
  const labels: Record<Urgency, string> = {
    routine: "routine",
    urgent: "urgent",
    emergency: "emergency",
  };
  return (
    <span
      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${s.bg} ${s.text} ${s.pulse ? "animate-pulse" : ""}`}
    >
      {labels[urgency]}
    </span>
  );
}

export default function MainContentList({
  onSessionSelect,
}: {
  onSessionSelect?: (id: string) => void;
}) {
  const [groupBy, setGroupBy] = useState("status");
  const todos = SESSIONS.filter((s) => s.status === "todo");
  const inProgress = SESSIONS.filter((s) => s.status === "in_progress");

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Filter bar */}
      <div className="shrink-0 px-4 py-2 border-b border-[#E8E8F0] bg-[#FFFFFF] flex items-center gap-3">
        <span className="text-[12px] text-[#6B6B8A]">Group:</span>
        <button
          type="button"
          onClick={() => setGroupBy("status")}
          className={`text-[12px] font-semibold px-2 py-1 rounded ${
            groupBy === "status" ? "bg-[#EEF0FF] text-[#7B68EE]" : "text-[#1B1B2F] hover:bg-[#F5F5FA]"
          }`}
        >
          Status
        </button>
        <span className="text-[12px] text-[#6B6B8A]">|</span>
        <span className="text-[12px] text-[#6B6B8A]">Subtasks</span>
      </div>

      {/* List content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <div className="text-[13px] font-bold text-[#1B1B2F] mb-2 flex items-center gap-2">
            <LayoutList className="w-[16px] h-[16px]" />
            Ca khám hôm nay
          </div>

          {/* TO DO */}
          <div className="mb-4">
            <div className="text-[11px] font-semibold text-[#6B6B8A] uppercase tracking-wide mb-2">
              TO DO ({todos.length})
            </div>
            <div className="space-y-1">
              {todos.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => onSessionSelect?.(s.id)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#F5F5FA] text-left border border-transparent hover:border-[#E8E8F0]"
                >
                  <span className="text-[#6B6B8A]">○</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-[#1B1B2F] truncate">
                      {s.name} — {s.symptoms}
                    </div>
                  </div>
                  <UrgencyBadge urgency={s.urgency} />
                </button>
              ))}
              <button
                type="button"
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-[#F5F5FA] text-[#7B68EE] text-[12px] font-semibold"
              >
                <Plus className="w-[14px] h-[14px]" />
                Thêm ca khám
              </button>
            </div>
          </div>

          {/* IN PROGRESS */}
          <div>
            <div className="text-[11px] font-semibold text-[#6B6B8A] uppercase tracking-wide mb-2">
              IN PROGRESS ({inProgress.length})
            </div>
            <div className="space-y-1">
              {inProgress.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => onSessionSelect?.(s.id)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#F5F5FA] text-left border border-transparent hover:border-[#E8E8F0]"
                >
                  <span className="text-[#7B68EE]">●</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-[#1B1B2F] truncate">
                      {s.name} — {s.symptoms}
                    </div>
                  </div>
                  <UrgencyBadge urgency={s.urgency} />
                </button>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
