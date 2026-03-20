"use client";

import React from "react";
import { Bot, Copy, Search, Settings2, Share2 } from "lucide-react";

export default function TopBar({
  onOpenCommandPalette,
  pageTitle = "Home — Tự Minh Platform",
}: {
  onOpenCommandPalette: () => void;
  pageTitle?: string;
}) {
  return (
    <header className="h-[56px] bg-[#FFFFFF] border-b border-[#E8E8F0] flex items-center px-4">
      <div className="flex items-center gap-3 w-[260px] shrink-0 min-w-0">
        <div className="text-[13px] font-semibold text-[#1B1B2F] truncate">{pageTitle}</div>
        <div className="h-4 w-px bg-[#E8E8F0]" />
        <div className="text-[12px] text-[#6B6B8A] flex items-center gap-2">
          <span aria-hidden className="text-[14px]">
            🌿
          </span>
          <span className="px-2 py-1 rounded-full bg-[#F0F0F8]">Bệnh nhân</span>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="w-full max-w-[520px] h-[36px] rounded-xl bg-[#F0F0F8] hover:bg-[#F0F0F8]/80 ring-1 ring-black/5 flex items-center px-3 gap-2 text-left"
        >
          <Search className="w-[16px] h-[16px] text-[#6B6B8A]" />
          <span className="text-[13px] text-[#6B6B8A] truncate">
            Tìm kiếm bệnh, thuốc, triệu chứng... CtrlK
          </span>
        </button>
      </div>

      <div className="w-[260px] flex items-center justify-end gap-2 shrink-0">
        <button
          type="button"
          className="h-[34px] px-3 rounded-full bg-[#FFFFFF] hover:bg-[#F0F0F8] text-[13px] text-[#1B1B2F] ring-1 ring-black/5 flex items-center gap-2"
        >
          <Bot className="w-[16px] h-[16px]" style={{ color: "#7B68EE" }} />
          Agents
        </button>
        <button
          type="button"
          className="h-[34px] px-3 rounded-full bg-[#FFFFFF] hover:bg-[#F0F0F8] text-[13px] text-[#1B1B2F] ring-1 ring-black/5 flex items-center gap-2"
        >
          <Settings2 className="w-[16px] h-[16px]" style={{ color: "#7B68EE" }} />
          Tự động hóa
        </button>
        <button
          type="button"
          className="h-[34px] px-3 rounded-full bg-[#FFFFFF] hover:bg-[#F0F0F8] text-[13px] text-[#1B1B2F] ring-1 ring-black/5 flex items-center gap-2"
        >
          <Share2 className="w-[16px] h-[16px]" style={{ color: "#7B68EE" }} />
          Chia sẻ
        </button>
        <button
          type="button"
          aria-label="Copy"
          className="h-[34px] w-[34px] rounded-xl bg-[#FFFFFF] hover:bg-[#F0F0F8] ring-1 ring-black/5 flex items-center justify-center"
        >
          <Copy className="w-[16px] h-[16px]" style={{ color: "#7B68EE" }} />
        </button>
      </div>
    </header>
  );
}

