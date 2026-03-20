"use client";

import React, { useEffect, useRef } from "react";
import { Grid } from "lucide-react";
import type { ModuleId } from "./moduleConfig";
import { MORE_GRID_MODULES, getModuleById } from "./moduleConfig";

const GRID_LABELS: Record<ModuleId, string> = {
  home: "Home",
  y_hoc: "Y học",
  code: "Code",
  hoc_tap: "Học tập",
  du_lieu: "Dữ liệu",
  cong_dong: "Cộng đồng",
  nghien_cuu: "Nghiên cứu",
  minh_bien: "Tự Minh",
  tu_dong: "Tự động",
  workspace: "Workspace",
  ghi_chu: "Ghi chú",
  muc_tieu: "Mục tiêu",
  thoi_gian: "Thời gian",
};

const GRID_EMOJIS: Record<ModuleId, string> = {
  home: "🏠",
  y_hoc: "🌿",
  code: "💻",
  hoc_tap: "📚",
  du_lieu: "📊",
  cong_dong: "🤝",
  nghien_cuu: "🧬",
  minh_bien: "🤖",
  tu_dong: "⚡",
  workspace: "🗂️",
  ghi_chu: "📝",
  muc_tieu: "🎯",
  thoi_gian: "⏱️",
};

export default function MorePopup({
  isOpen,
  onClose,
  activeModule,
  onSelect,
  anchorRef,
}: {
  isOpen: boolean;
  onClose: () => void;
  activeModule: ModuleId;
  onSelect: (id: ModuleId) => void;
  anchorRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const popupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function onPointerDown(e: MouseEvent | TouchEvent) {
      const target = e.target as Node;
      if (
        popupRef.current?.contains(target) ||
        anchorRef.current?.contains(target)
      ) {
        return;
      }
      onClose();
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [isOpen, onClose, anchorRef]);

  if (!isOpen) return null;

  return (
    <div
      ref={popupRef}
      className="fixed left-[58px] top-[308px] z-[70] w-[280px] rounded-xl bg-white shadow-lg ring-1 ring-black/10 overflow-hidden"
      style={{ animation: "morePopupFadeIn 0.2s ease-out" }}
    >
      <style>{`
        @keyframes morePopupFadeIn {
          from { opacity: 0; transform: translateX(-4px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>

      {/* Header */}
      <div className="px-3 py-2.5 border-b border-[#E8E8F0] flex items-center justify-between">
        <span className="text-[13px] font-semibold text-[#1B1B2F]">
          Tất cả modules
        </span>
        <button
          type="button"
          className="text-[12px] font-medium text-[#7B68EE] hover:underline"
        >
          Tuỳ chỉnh
        </button>
      </div>

      {/* Grid 3 columns */}
      <div className="p-2 grid grid-cols-3 gap-1">
        {MORE_GRID_MODULES.map((id) => {
          const mod = getModuleById(id);
          const active = activeModule === id;
          const emoji = GRID_EMOJIS[id] ?? "📦";
          const label = GRID_LABELS[id] ?? id;

          return (
            <button
              key={id}
              type="button"
              onClick={() => {
                onSelect(id);
                onClose();
              }}
              className={[
                "h-[80px] flex flex-col items-center justify-center rounded-lg transition-colors",
                active
                  ? "bg-[#7B68EE] text-white"
                  : "hover:bg-[#EEEDFE] text-[#1B1B2F] hover:[&_span:last-child]:text-[#7B68EE]",
              ].join(" ")}
            >
              <span className="text-[28px] mb-1" aria-hidden>
                {emoji}
              </span>
              <span
                className={[
                  "text-[11px] font-medium truncate w-full px-1 text-center",
                  active ? "text-white" : "",
                ].join(" ")}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-3 py-2 border-t border-[#E8E8F0]">
        <button
          type="button"
          className="w-full text-[12px] font-medium text-[#7B68EE] hover:underline text-center"
        >
          Tuỳ chỉnh điều hướng
        </button>
      </div>
    </div>
  );
}
