"use client";

import React, { useRef, useState, useCallback } from "react";
import IconNav from "./IconNav";
import MorePopup from "./MorePopup";
import ResizeHandle from "./ResizeHandle";
import SidebarTree from "./SidebarTree";
import TopBar from "./TopBar";
import TabRow from "./TabRow";
import HealthProfileCard from "../HealthProfileCard";
import type { ModuleId } from "./moduleConfig";

const PANEL_MIN = 240;
const PANEL_MAX = 480;
const PANEL_DEFAULT = 320;

export default function ClickUpShell({
  onOpenCommandPalette,
  activeModule,
  onSelectModule,
  pageTitle,
  main,
  agentPanel,
  isEmergency = false,
}: {
  onOpenCommandPalette: () => void;
  activeModule: ModuleId;
  onSelectModule: (id: ModuleId) => void;
  pageTitle: string;
  main: React.ReactNode;
  agentPanel: React.ReactNode;
  isEmergency?: boolean;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT);
  const [mobileAgentOpen, setMobileAgentOpen] = useState(false);
  const moreButtonRef = useRef<HTMLButtonElement | null>(null);
  const onOpenHealthProfile = useCallback(() => {
    console.log("open health profile");
  }, []);

  return (
    <div className="min-h-screen bg-[#F8F8FC] text-[#1B1B2F]">
      <div className="h-screen flex overflow-hidden">
        <div className="hidden xl:flex shrink-0 relative">
          <IconNav
            activeModule={activeModule}
            onSelectModule={onSelectModule}
            onToggleMore={() => setMoreOpen((v) => !v)}
            moreOpen={moreOpen}
            moreButtonRef={moreButtonRef}
          />
          <MorePopup
            isOpen={moreOpen}
            onClose={() => setMoreOpen(false)}
            activeModule={activeModule}
            onSelect={onSelectModule}
            anchorRef={moreButtonRef}
          />
        </div>

        <div className="flex-1 flex flex-col min-w-0">
          <TopBar
            onOpenCommandPalette={onOpenCommandPalette}
            pageTitle={pageTitle}
          />
          <TabRow />

          <div className="flex flex-1 min-h-0 overflow-hidden">
            <div className="hidden lg:block shrink-0">
              <SidebarTree />
            </div>

            <main className="flex-1 min-w-0 overflow-hidden">{main}</main>

            <div className="hidden md:flex shrink-0">
              <ResizeHandle
                currentWidth={panelWidth}
                minWidth={PANEL_MIN}
                maxWidth={PANEL_MAX}
                onResize={setPanelWidth}
              />
            </div>

            <HealthProfileCard
              isEmergency={isEmergency}
              onOpenProfile={onOpenHealthProfile}
            />

            <aside
              className="hidden md:block shrink-0 overflow-hidden border-l border-[#E8E8F0]"
              style={{ width: panelWidth, minWidth: PANEL_MIN, maxWidth: PANEL_MAX }}
            >
              {agentPanel}
            </aside>
          </div>

          <div className="md:hidden fixed bottom-0 left-0 right-0 h-[52px] bg-[#FFFFFF] border-t border-[#E8E8F0] z-[60] flex items-center justify-around">
            {["Home", "Y học", "Settings"].map((t) => (
              <div key={t} className="text-[12px] font-semibold text-[#6B6B8A]">
                {t}
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setMobileAgentOpen(true)}
            className="md:hidden fixed bottom-20 right-4 w-[56px] h-[56px] rounded-full bg-[#7B68EE] text-white shadow-lg flex items-center justify-center text-2xl z-[70]"
            aria-label="Mở Tự Minh"
          >
            🤖
          </button>

          {mobileAgentOpen && (
            <>
              <div
                className="md:hidden fixed inset-0 bg-black/40 z-[75]"
                onClick={() => setMobileAgentOpen(false)}
                aria-hidden
              />
              <div
                className="md:hidden fixed inset-x-0 bottom-0 z-[80] h-[80vh] rounded-t-2xl bg-[#FFFFFF] shadow-xl overflow-hidden flex flex-col"
                style={{ animation: "minhbien-slideUp 0.3s ease-out" }}
              >
                <div className="flex items-center justify-between px-3 py-2 border-b border-[#E8E8F0]">
                  <span className="text-[13px] font-bold">Tự Minh</span>
                  <button
                    type="button"
                    onClick={() => setMobileAgentOpen(false)}
                    className="text-[#6B6B8A] px-2 py-1"
                  >
                    Đóng
                  </button>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                  {agentPanel}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes minhbien-slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}} />
    </div>
  );
}
