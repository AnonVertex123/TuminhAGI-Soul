"use client";

import React from "react";
import {
  Home,
  HeartPulse,
  Code2,
  BookOpen,
  BarChart2,
  Users,
  Grid,
  Settings,
  UserCircle,
  Zap,
} from "lucide-react";
import type { ModuleId } from "./moduleConfig";
import { NAV_STRIP_MODULES, getModuleById } from "./moduleConfig";

type NavStripItem = {
  id: ModuleId | "more";
  label: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  activeColor?: string;
};

const STRIP_ITEMS: NavStripItem[] = [
  { id: "home", label: "Home", Icon: Home, activeColor: "#5F5E5A" },
  { id: "y_hoc", label: "🌿 Y học", Icon: HeartPulse, activeColor: "#0F6E56" },
  { id: "code", label: "💻 Code", Icon: Code2, activeColor: "#7B68EE" },
  { id: "hoc_tap", label: "📚 Học tập", Icon: BookOpen, activeColor: "#185FA5" },
  { id: "du_lieu", label: "📊 Dữ liệu", Icon: BarChart2, activeColor: "#854F0B" },
  { id: "cong_dong", label: "🤝 Cộng đồng", Icon: Users, activeColor: "#993C1D" },
  { id: "more", label: "••• More", Icon: Grid, activeColor: "#5F5E5A" },
];

export default function IconNav({
  activeModule,
  onSelectModule,
  onToggleMore,
  moreOpen,
  moreButtonRef,
}: {
  activeModule: ModuleId;
  onSelectModule: (id: ModuleId) => void;
  onToggleMore: () => void;
  moreOpen: boolean;
  moreButtonRef?: React.RefObject<HTMLButtonElement | null>;
}) {
  return (
    <nav className="relative w-[50px] bg-[#FFFFFF] border-r border-[#E8E8F0] shrink-0 flex flex-col h-screen">
      <div className="flex-1 flex flex-col items-center pt-2 pb-2 gap-0">
        {STRIP_ITEMS.map((it) => {
          const isMore = it.id === "more";
          const active = !isMore && it.id === activeModule;
          const iconColor = active ? (it.activeColor ?? "#5F5E5A") : "#6B6B8A";

          return (
            <div key={it.id} className="relative group">
              <button
                ref={isMore ? (moreButtonRef as React.Ref<HTMLButtonElement>) : undefined}
                type="button"
                aria-label={it.label}
                aria-expanded={isMore ? moreOpen : undefined}
                onClick={() => {
                  if (isMore) {
                    onToggleMore();
                  } else {
                    onSelectModule(it.id as ModuleId);
                  }
                }}
                className={[
                  "w-[50px] h-[50px] flex items-center justify-center relative transition-colors",
                  active || (isMore && moreOpen)
                    ? ""
                    : "hover:bg-[#F5F5FA]",
                  active || (isMore && moreOpen) ? "bg-[#F5F5FA]" : "",
                ].join(" ")}
              >
                {active ? (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 h-[24px] w-[3px] rounded-r"
                    style={{ backgroundColor: it.activeColor ?? "#5F5E5A" }}
                  />
                ) : null}
                <it.Icon
                  className="w-[20px] h-[20px] shrink-0"
                  color={iconColor}
                />
              </button>
              {/* CSS-only tooltip — appears on right */}
              <span
                className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1.5 rounded-md bg-[#1B1B2F] text-white text-[11px] font-medium whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[80]"
                role="tooltip"
              >
                {it.label}
              </span>
            </div>
          );
        })}

        <div className="mt-auto flex flex-col items-center gap-0 pt-2">
          <div className="relative group">
            <button
              type="button"
              aria-label="Settings"
              className="w-[50px] h-[50px] flex items-center justify-center hover:bg-[#F5F5FA] transition-colors"
            >
              <Settings
                className="w-[20px] h-[20px] shrink-0"
                style={{ color: "#6B6B8A" }}
              />
            </button>
            <span
              className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1.5 rounded-md bg-[#1B1B2F] text-white text-[11px] font-medium whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[80]"
              role="tooltip"
            >
              Settings
            </span>
          </div>
          <div className="relative group">
            <button
              type="button"
              aria-label="User"
              className="w-[50px] h-[50px] flex items-center justify-center hover:bg-[#F5F5FA] transition-colors"
            >
              <UserCircle
                className="w-[20px] h-[20px] shrink-0"
                style={{ color: "#6B6B8A" }}
              />
            </button>
            <span
              className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1.5 rounded-md bg-[#1B1B2F] text-white text-[11px] font-medium whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[80]"
              role="tooltip"
            >
              User
            </span>
          </div>
          <div className="relative group">
            <button
              type="button"
              aria-label="Upgrade"
              className="w-[50px] h-[50px] flex items-center justify-center hover:bg-[#F5F5FA] transition-colors relative"
            >
              <Zap
                className="w-[20px] h-[20px] shrink-0"
                style={{ color: "#7B68EE" }}
              />
              <span className="absolute top-2 right-2 w-[6px] h-[6px] rounded-full bg-[#7B68EE]" />
            </button>
            <span
              className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1.5 rounded-md bg-[#1B1B2F] text-white text-[11px] font-medium whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[80]"
              role="tooltip"
            >
              Upgrade
            </span>
          </div>
        </div>
      </div>
    </nav>
  );
}
