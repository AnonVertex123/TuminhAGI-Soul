"use client";

/**
 * StructuredOutputPanel — TuminhAGI Output Layer V2.0
 * Renders the 4-section safe, descriptive output.
 * Never uses assertive diagnostic language.
 */

import React from "react";

// ── Types ──────────────────────────────────────────────────────────────────

export interface PossibleCondition {
  icd_reference: string;
  name: string;
  description_phrase: string;
  similarity: number;
  confidence: number | null;
  critic_status: string;
}

export interface StructuredOutputData {
  symptom_summary: string;
  possible_conditions: PossibleCondition[];
  urgency: string;
  urgency_reason: string;
  doctor_note: string;
  gate_passed: boolean;
  gate_reason: string;
}

interface Props {
  data: StructuredOutputData | null;
}

// ── Urgency config ─────────────────────────────────────────────────────────

const URGENCY_CONFIG: Record<string, { icon: string; bg: string; text: string; badge: string }> = {
  "CẤP CỨU NGAY": {
    icon: "🚨",
    bg: "bg-red-50 dark:bg-red-950/40 border-red-300 dark:border-red-800",
    text: "text-red-700 dark:text-red-300",
    badge: "bg-red-600 text-white",
  },
  "Cần khám trong ngày": {
    icon: "⚠️",
    bg: "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800",
    text: "text-amber-700 dark:text-amber-300",
    badge: "bg-amber-500 text-white",
  },
  "Theo dõi tại nhà": {
    icon: "🟡",
    bg: "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800",
    text: "text-emerald-700 dark:text-emerald-300",
    badge: "bg-emerald-600 text-white",
  },
};

const CRITIC_STATUS_CONFIG: Record<string, { dot: string; label: string }> = {
  APPROVED:      { dot: "bg-emerald-500",  label: "Đáng tin cậy" },
  SUGGESTION:    { dot: "bg-amber-400",    label: "Cần xem xét thêm" },
  EMERGENCY_WARN:{ dot: "bg-orange-500",   label: "Cảnh báo cấp cứu" },
  UNKNOWN:       { dot: "bg-slate-400",    label: "Chưa phân loại" },
};

// ── Helper ─────────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <button
      onClick={copy}
      className="text-[11px] px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 hover:bg-emerald-100 dark:hover:bg-emerald-900 text-slate-600 dark:text-slate-300 transition-colors"
    >
      {copied ? "✓ Đã sao chép" : "Sao chép"}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function StructuredOutputPanel({ data }: Props) {
  if (!data) return null;

  // Gate blocked
  if (!data.gate_passed) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900 p-4 mt-3">
        <div className="flex items-start gap-2">
          <span className="text-lg">⛔</span>
          <div>
            <p className="text-[13px] font-semibold text-slate-700 dark:text-slate-200">
              Không thể đưa ra thông tin tham khảo
            </p>
            <p className="text-[12px] text-slate-500 dark:text-slate-400 mt-0.5">
              {data.gate_reason}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const urgencyCfg = URGENCY_CONFIG[data.urgency] ?? URGENCY_CONFIG["Theo dõi tại nhà"];

  return (
    <div className="space-y-3 mt-3">
      {/* ── Section 1: Symptom Summary ── */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900 p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base">📋</span>
          <h4 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Tóm tắt triệu chứng
          </h4>
        </div>
        <p className="text-[13px] text-slate-700 dark:text-slate-200 leading-relaxed">
          {data.symptom_summary}
        </p>
      </div>

      {/* ── Section 2: Possible Conditions ── */}
      {data.possible_conditions.length > 0 && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">🔍</span>
            <h4 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Các khả năng có thể xảy ra
            </h4>
          </div>
          <div className="space-y-3">
            {data.possible_conditions.map((cond, i) => {
              const sc = CRITIC_STATUS_CONFIG[cond.critic_status] ?? CRITIC_STATUS_CONFIG.UNKNOWN;
              return (
                <div key={i} className="flex gap-3">
                  <div className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${sc.dot}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[13px] font-medium text-slate-800 dark:text-slate-100">
                        {cond.name}
                      </span>
                      {cond.confidence !== null && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                          {cond.confidence}%
                        </span>
                      )}
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        {sc.label}
                      </span>
                    </div>
                    <p className="text-[12px] text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
                      {cond.description_phrase}
                    </p>
                    {cond.icd_reference && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                        ICD-10: {cond.icd_reference}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            * Thông tin trên chỉ mang tính tham khảo, không thay thế chẩn đoán của bác sĩ.
          </p>
        </div>
      )}

      {/* ── Section 3: Urgency Triage ── */}
      <div className={`rounded-xl border p-4 ${urgencyCfg.bg}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-base">{urgencyCfg.icon}</span>
          <h4 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Phân tầng mức độ nguy hiểm
          </h4>
        </div>
        <div className={`inline-block px-2.5 py-0.5 rounded-full text-[12px] font-semibold mt-1 mb-2 ${urgencyCfg.badge}`}>
          {urgencyCfg.icon} {data.urgency}
        </div>
        {data.urgency_reason && (
          <p className={`text-[12px] leading-relaxed ${urgencyCfg.text}`}>
            {data.urgency_reason}
          </p>
        )}
      </div>

      {/* ── Section 4: Doctor's Note ── */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900 p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-base">📄</span>
            <h4 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Bản tin cho Bác sĩ
            </h4>
          </div>
          <CopyButton text={data.doctor_note} />
        </div>
        <blockquote className="text-[12px] text-slate-600 dark:text-slate-300 leading-relaxed border-l-2 border-emerald-400 pl-3 italic">
          {data.doctor_note}
        </blockquote>
      </div>
    </div>
  );
}
