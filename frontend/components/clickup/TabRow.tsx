"use client";

import React from "react";
import { Plus } from "lucide-react";

type Tab = {
  id: string;
  label: string;
  active?: boolean;
  Icon?: React.ComponentType<{ className?: string; color?: string }>;
};

const TABS: Tab[] = [
  { id: "channel", label: "Channel", active: false },
  { id: "list", label: "List", active: true },
  { id: "board", label: "Board", active: false },
  { id: "calendar", label: "Calendar", active: false },
  { id: "view", label: "+ View", Icon: Plus, active: false },
];

export default function TabRow() {
  return (
    <div className="h-[44px] bg-[#FFFFFF] border-b border-[#E8E8F0] flex items-center px-4 gap-3 overflow-hidden">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={[
            "h-[28px] rounded-xl px-3 text-[13px] font-medium ring-1 ring-black/5 transition-colors whitespace-nowrap",
            t.active
              ? "bg-[#EEF0FF] text-[#7B68EE] ring-[#E8E8F0]"
              : "bg-transparent hover:bg-[#F0F0F8] text-[#1B1B2F]",
          ].join(" ")}
        >
          {t.Icon ? (
            <t.Icon
              className="w-[14px] h-[14px] inline-block mr-1"
              color="#7B68EE"
            />
          ) : null}
          {t.label}
        </button>
      ))}
    </div>
  );
}

