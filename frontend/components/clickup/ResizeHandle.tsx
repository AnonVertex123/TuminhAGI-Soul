"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

export default function ResizeHandle({
  onResize,
  minWidth = 240,
  maxWidth = 480,
  currentWidth = 320,
}: {
  onResize: (width: number) => void;
  minWidth?: number;
  maxWidth?: number;
  currentWidth?: number;
}) {
  const [dragging, setDragging] = useState(false);
  const startRef = useRef({ x: 0, w: currentWidth });

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      startRef.current = { x: e.clientX, w: currentWidth };
      setDragging(true);
    },
    [currentWidth]
  );

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (e: PointerEvent) => {
      const { x, w } = startRef.current;
      const dx = x - e.clientX;
      const next = Math.min(maxWidth, Math.max(minWidth, w + dx));
      onResize(next);
    };
    const handleUp = () => setDragging(false);
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    (document.body as HTMLElement).style.cursor = "col-resize";
    (document.body as HTMLElement).style.userSelect = "none";
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      (document.body as HTMLElement).style.cursor = "";
      (document.body as HTMLElement).style.userSelect = "";
    };
  }, [dragging, minWidth, maxWidth, onResize]);

  return (
    <div
      onPointerDown={handlePointerDown}
      className="w-1 shrink-0 bg-transparent hover:bg-[#7B68EE]/30 cursor-col-resize flex-shrink-0 group transition-colors"
      style={{ minWidth: 4 }}
      role="separator"
      aria-orientation="vertical"
    >
      <div className="w-full h-full flex items-center justify-center">
        <div className="w-0.5 h-8 rounded-full bg-[#E8E8F0] group-hover:bg-[#7B68EE] opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  );
}
