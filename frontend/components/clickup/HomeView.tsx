"use client";

import React from "react";
import type { ModuleId } from "./moduleConfig";
import { MODULES } from "./moduleConfig";

export default function HomeView({
  onSelectModule,
}: {
  onSelectModule: (id: ModuleId) => void;
}) {
  const featured = MODULES.filter((m) =>
    ["y_hoc", "code", "hoc_tap", "du_lieu"].includes(m.id)
  );

  return (
    <div className="h-full overflow-y-auto flex items-center justify-center p-6 bg-gradient-to-br from-[#F8F8FC] to-[#EEEDFE]">
      <div className="w-full max-w-[480px] text-center">
          <h1 className="text-[24px] font-bold text-[#1B1B2F] mb-2">
          Chào mừng đến Tự Minh Platform
        </h1>
        <p className="text-[14px] text-[#6B6B8A] mb-8">
          Tự Minh sẽ đồng hành cùng bạn
        </p>
        <div className="grid grid-cols-2 gap-3">
          {featured.map((mod) => (
            <button
              key={mod.id}
              type="button"
              onClick={() => onSelectModule(mod.id)}
              className="rounded-xl p-4 text-left ring-1 ring-black/5 hover:ring-2 transition-all flex items-center gap-3"
              style={{ backgroundColor: mod.bgColor }}
            >
              <span className="text-[28px]" aria-hidden>
                {mod.emoji}
              </span>
              <div>
                <div
                  className="text-[13px] font-semibold"
                  style={{ color: mod.color }}
                >
                  {mod.shortLabel}
                </div>
                <div className="text-[11px] text-[#6B6B8A] truncate">
                  {mod.description.slice(0, 30)}…
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
