"use client";

import React from "react";
import type { ModuleConfig } from "./moduleConfig";

export default function ComingSoonPlaceholder({ module: mod }: { module: ModuleConfig }) {
  return (
    <div
      className="min-h-full flex items-center justify-center p-6"
      style={{ background: `linear-gradient(135deg, ${mod.bgColor} 0%, rgba(255,255,255,0.95) 100%)` }}
    >
      <div className="w-full max-w-[360px] rounded-2xl bg-white/90 backdrop-blur-sm shadow-lg ring-1 ring-black/5 overflow-hidden">
        <div className="p-8 text-center">
          <div
            className="w-[72px] h-[72px] mx-auto mb-4 rounded-2xl flex items-center justify-center text-[36px]"
            style={{ backgroundColor: mod.bgColor }}
            aria-hidden
          >
            {mod.emoji}
          </div>
          <h2 className="text-[18px] font-bold text-[#1B1B2F] mb-1">{mod.shortLabel}</h2>
          <p className="text-[13px] text-[#6B6B8A] leading-relaxed mb-6">{mod.description}</p>

          <div className="rounded-xl bg-[#F8F8FC] ring-1 ring-black/5 px-4 py-3 mb-6">
            <p className="text-[12px] text-[#6B6B8A] font-medium">
              🚧 Đang trong lộ trình phát triển của Tự Minh Platform
            </p>
            {mod.phase ? (
              <p className="text-[11px] text-[#7B68EE] font-semibold mt-1">Dự kiến: {mod.phase}</p>
            ) : null}
          </div>

          <button
            type="button"
            className="h-[40px] px-6 rounded-full text-[13px] font-semibold text-white transition-opacity hover:opacity-95"
            style={{ backgroundColor: mod.color }}
          >
            Nhận thông báo khi ra mắt
          </button>
        </div>
      </div>
    </div>
  );
}
