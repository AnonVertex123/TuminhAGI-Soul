"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

const HEALTH_PROFILE = {
  name: "Nguyễn Văn A",
  age: 45,
  sex: "Nam",
  conditions: ["Huyết áp cao (I10)"],
  medications: ["Amlodipine 5mg"],
  constitution: "Âm hư",
  allergies: ["Penicillin"],
  reminders: [{ time: "08:00", text: "Uống thuốc huyết áp" }],
  nextAppointment: "15/04/2026",
  lastCheckup: "2 ngày trước",
};

const TOTAL_SECONDS = 25;
const IDLE_MS = 5000; // 5s of no activity to resume timer
const COOLDOWN_MS = 10 * 60 * 1000; // 10 min after dismiss
const STORAGE_KEY = "tuminh_health_card_dismissed";

export default function HealthProfileCard({
  isEmergency = false,
  onOpenProfile,
  onDismiss,
}: {
  isEmergency?: boolean;
  onOpenProfile?: () => void;
  onDismiss?: () => void;
}) {
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hover, setHover] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const showTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastActivityRef = useRef(Date.now());
  const idleCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  const clearShowTimeout = useCallback(() => {
    if (showTimeoutRef.current) {
      clearTimeout(showTimeoutRef.current);
      showTimeoutRef.current = null;
    }
  }, []);

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const dismiss = useCallback(() => {
    setExiting(true);
    clearTimer();
    clearShowTimeout();
    onDismiss?.();
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, String(Date.now()));
    }
    setTimeout(() => setVisible(false), 200);
  }, [clearTimer, clearShowTimeout, onDismiss]);

  const shouldShow = useCallback(() => {
    if (isEmergency) return false;
    const dismissedAt = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (dismissedAt) {
      const diff = Date.now() - Number(dismissedAt);
      if (diff < COOLDOWN_MS) return false;
    }
    return true;
  }, [isEmergency]);

  // Show card 2s after load
  useEffect(() => {
    if (!shouldShow()) return;
    showTimeoutRef.current = setTimeout(() => {
      setVisible(true);
    }, 2000);
    return clearShowTimeout;
  }, [shouldShow, clearShowTimeout]);

  // Don't show when emergency becomes true
  useEffect(() => {
    if (isEmergency && visible) {
      setExiting(true);
      clearTimer();
      clearShowTimeout();
      setTimeout(() => setVisible(false), 200);
    }
  }, [isEmergency, visible, clearTimer, clearShowTimeout]);

  // Countdown timer
  useEffect(() => {
    if (!visible || exiting || paused || hover) return;
    intervalRef.current = setInterval(() => {
      setElapsed((e) => {
        const next = e + 1;
        if (next >= TOTAL_SECONDS) {
          clearTimer();
          dismiss();
        }
        return next;
      });
    }, 1000);
    return clearTimer;
  }, [visible, exiting, paused, hover, dismiss, clearTimer]);

  // Pause on user activity elsewhere (not on card), resume when idle
  useEffect(() => {
    const handleActivity = (e: Event) => {
      const target = e.target as Node;
      if (visible && !hover && cardRef.current && !cardRef.current.contains(target)) {
        lastActivityRef.current = Date.now();
        setPaused(true);
      }
    };
    idleCheckRef.current = setInterval(() => {
      if (!visible || hover) return;
      if (Date.now() - lastActivityRef.current >= IDLE_MS) setPaused(false);
    }, 500);
    window.addEventListener("keydown", handleActivity);
    window.addEventListener("click", handleActivity);
    return () => {
      window.removeEventListener("keydown", handleActivity);
      window.removeEventListener("click", handleActivity);
      if (idleCheckRef.current) clearInterval(idleCheckRef.current);
    };
  }, [visible, hover]);

  const progress = Math.min(1, elapsed / TOTAL_SECONDS);
  const progressColor =
    progress >= (TOTAL_SECONDS - 2) / TOTAL_SECONDS
      ? "#DC2626"
      : progress >= (TOTAL_SECONDS - 5) / TOTAL_SECONDS
        ? "#D97706"
        : "#0F6E56";

  if (!visible) return null;

  return (
    <div
      ref={cardRef}
      data-health-card
      className="fixed top-[70px] right-2 z-[50] w-[300px]"
      style={{
        animation: exiting
          ? "healthCardSlideOut 0.2s ease-in forwards"
          : "healthCardSlideIn 0.3s ease-out",
      }}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes healthCardSlideIn {
          from { transform: translateX(320px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes healthCardSlideOut {
          from { transform: translateX(0); opacity: 1; }
          to { transform: translateX(320px); opacity: 0; }
        }
      `}} />
      <div
        role="button"
        tabIndex={0}
        onClick={() => {
          console.log("open health profile");
          onOpenProfile?.();
        }}
        onKeyDown={(e) => e.key === "Enter" && (console.log("open health profile"), onOpenProfile?.())}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className="rounded-xl bg-white shadow-lg border border-[#E8E8F0] overflow-hidden cursor-pointer transition-transform hover:scale-[1.01] hover:shadow-xl"
        style={{ borderLeftWidth: 4, borderLeftColor: "#0F6E56" }}
      >
        {/* Progress bar */}
        <div className="h-1 bg-[#E8E8F0] overflow-hidden">
          <div
            className="h-full transition-all duration-1000 linear"
            style={{
              width: `${(1 - progress) * 100}%`,
              backgroundColor: progressColor,
            }}
          />
        </div>

        <div className="p-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[13px] font-bold text-[#1B1B2F] flex items-center gap-1">
                <span aria-hidden>👤</span> Hồ sơ sức khỏe
              </div>
              <div className="text-[11px] text-[#6B6B8A] mt-0.5">
                {HEALTH_PROFILE.name} · {HEALTH_PROFILE.age}t · {HEALTH_PROFILE.sex}
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                dismiss();
              }}
              className="shrink-0 p-1 rounded hover:bg-[#F5F5FA] text-[#6B6B8A]"
              aria-label="Đóng"
            >
              <X className="w-[16px] h-[16px]" />
            </button>
          </div>

          <div className="border-t border-[#E8E8F0] my-2" />

          {/* Conditions */}
          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center gap-1.5">
              <span aria-hidden>🏥</span>
              <span className="text-[#1B1B2F]">{HEALTH_PROFILE.conditions[0]}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span aria-hidden>💊</span>
              <span className="text-[#1B1B2F]">{HEALTH_PROFILE.medications[0]}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span aria-hidden>🌿</span>
              <span className="text-[#1B1B2F]">Thể trạng: {HEALTH_PROFILE.constitution}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span aria-hidden>⚠️</span>
              <span className="text-amber-700">Dị ứng: {HEALTH_PROFILE.allergies[0]}</span>
            </div>
          </div>

          <div className="border-t border-[#E8E8F0] my-2" />

          {/* Reminder & next appointment */}
          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center gap-1.5">
              <span aria-hidden>🔔</span>
              <span className="text-[#1B1B2F]">Nhắc: {HEALTH_PROFILE.reminders[0].text} lúc {HEALTH_PROFILE.reminders[0].time}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span aria-hidden>📅</span>
              <span className="text-[#1B1B2F]">Tái khám: {HEALTH_PROFILE.nextAppointment}</span>
            </div>
          </div>

          <div className="border-t border-[#E8E8F0] mt-2 pt-2">
            <div className="text-[11px] font-semibold text-[#0F6E56]">
              Xem hồ sơ đầy đủ →
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
