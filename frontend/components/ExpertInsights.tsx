"use client";

import React, { useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types (mirror professor_reasoning.py dataclasses)
// ─────────────────────────────────────────────────────────────────────────────

export interface AdjustedItem {
  code: string;
  description: string;
  base_prob: number;
  adjusted_prob: number;
  expert_label: string;
  is_red_flag: boolean;
}

export interface RedFlag {
  code: string;
  name: string;
  urgency: "CRITICAL" | "HIGH";
  reason: string;
  triggered_by: string[];
}

export interface PathognomicBoost {
  pattern_name: string;
  matched_keywords: string[];
  boost_factor: number;
  boosted_codes: string[];
  note: string;
}

export interface DifferentialExclusion {
  code: string;
  name: string;
  expected_hallmark: string;
  exclusion_question: string;
}

export interface ExpertInsightPayload {
  adjusted_items: AdjustedItem[];
  red_flags: RedFlag[];
  pathognomonic_boosts: PathognomicBoost[];
  differential_exclusions: DifferentialExclusion[];
  expert_summary: string;
  latency_ms: number;
}

interface Props {
  insight: ExpertInsightPayload | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function RedFlagCard({ rf }: { rf: RedFlag }) {
  const isCritical = rf.urgency === "CRITICAL";
  return (
    <div
      className={`rounded-lg border px-3 py-2 mb-2 ${
        isCritical
          ? "border-red-500 bg-red-950/40"
          : "border-amber-500 bg-amber-950/30"
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-lg leading-none mt-0.5">
          {isCritical ? "⛔" : "⚠️"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                isCritical
                  ? "bg-red-600 text-white"
                  : "bg-amber-600 text-white"
              }`}
            >
              {rf.urgency}
            </span>
            <span className="text-sm font-semibold text-white truncate">
              {rf.name}
            </span>
          </div>
          <p className="text-xs text-gray-300 mt-1 leading-relaxed">
            {rf.reason}
          </p>
          {rf.triggered_by.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {rf.triggered_by.map((k) => (
                <span
                  key={k}
                  className="text-xs px-1.5 py-0.5 rounded bg-red-900/60 text-red-300"
                >
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProbBar({ item }: { item: AdjustedItem }) {
  const pct = Math.min(item.adjusted_prob, 100);
  const delta = item.adjusted_prob - item.base_prob;
  const barColor = item.is_red_flag
    ? "bg-red-500"
    : pct >= 60
    ? "bg-amber-400"
    : pct >= 35
    ? "bg-emerald-400"
    : "bg-slate-400";

  return (
    <div className="mb-2">
      <div className="flex items-center justify-between mb-0.5 gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {item.is_red_flag && (
            <span className="text-red-400 text-xs shrink-0">🔴</span>
          )}
          <span className="text-xs font-mono text-emerald-300 shrink-0">
            {item.code}
          </span>
          <span className="text-xs text-gray-300 truncate">
            {item.description}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {delta !== 0 && (
            <span
              className={`text-xs ${
                delta > 0 ? "text-amber-400" : "text-slate-400"
              }`}
            >
              {delta > 0 ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}%
            </span>
          )}
          <span className="text-xs font-semibold text-white w-10 text-right">
            {pct.toFixed(1)}%
          </span>
        </div>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-xs text-gray-500 mt-0.5">{item.expert_label}</div>
    </div>
  );
}

function ExclusionCard({ ex }: { ex: DifferentialExclusion }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-1.5 border border-slate-700 rounded-lg overflow-hidden">
      <button
        className="w-full text-left px-3 py-2 flex items-center justify-between hover:bg-slate-700/40 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-amber-400 text-xs shrink-0">💬</span>
          <span className="text-xs font-mono text-emerald-300 shrink-0">
            {ex.code}
          </span>
          <span className="text-xs text-gray-300 truncate">{ex.name}</span>
        </div>
        <span className="text-gray-500 text-xs ml-2">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 bg-slate-800/30">
          <p className="text-xs text-amber-200 italic leading-relaxed">
            "{ex.exclusion_question}"
          </p>
          <p className="text-xs text-gray-400 mt-1">
            <span className="text-gray-500">Cần có:</span>{" "}
            {ex.expected_hallmark}
          </p>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

type Tab = "overview" | "redflags" | "exclusions";

export default function ExpertInsights({ insight }: Props) {
  const [tab, setTab] = useState<Tab>("overview");

  if (!insight) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">🎓</span>
          <span className="text-sm font-semibold text-slate-300">
            Lời Khuyên Chuyên Gia (PGS)
          </span>
        </div>
        <p className="text-xs text-slate-500 italic">
          Chờ kết quả chẩn đoán để phân tích biện chứng lâm sàng…
        </p>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "overview", label: "Tổng quan" },
    {
      id: "redflags",
      label: "Red Flags",
      count: insight.red_flags.length,
    },
    {
      id: "exclusions",
      label: "Loại trừ",
      count: insight.differential_exclusions.length,
    },
  ];

  const hasCritical = insight.red_flags.some((r) => r.urgency === "CRITICAL");

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 overflow-hidden">
      {/* Header */}
      <div
        className={`px-4 py-2.5 flex items-center justify-between ${
          hasCritical
            ? "bg-red-950/60 border-b border-red-800/50"
            : "bg-slate-800 border-b border-slate-700"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-base">🎓</span>
          <span className="text-sm font-bold text-white">
            Biện Chứng Lâm Sàng
          </span>
          {hasCritical && (
            <span className="text-xs bg-red-600 text-white px-1.5 py-0.5 rounded font-semibold animate-pulse">
              KHẨN
            </span>
          )}
        </div>
        <span className="text-xs text-slate-500">
          {insight.latency_ms.toFixed(1)} ms
        </span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 bg-slate-800/40">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 text-xs py-2 px-2 font-medium transition-colors ${
              tab === t.id
                ? "text-emerald-400 border-b-2 border-emerald-400 bg-slate-700/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span
                className={`ml-1 text-xs px-1 rounded-full ${
                  t.id === "redflags"
                    ? "bg-red-600 text-white"
                    : "bg-slate-600 text-slate-200"
                }`}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="p-3 max-h-[420px] overflow-y-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-slate-600">
        {/* ── Overview tab ── */}
        {tab === "overview" && (
          <div>
            {/* Pathognomonic boosts */}
            {insight.pathognomonic_boosts.length > 0 && (
              <div className="mb-3">
                <p className="text-xs font-semibold text-amber-300 mb-1.5 flex items-center gap-1">
                  🎯 Dấu Hiệu Đặc Trưng (Pathognomonic)
                </p>
                {insight.pathognomonic_boosts.map((b, i) => (
                  <div
                    key={i}
                    className="mb-2 bg-amber-950/30 border border-amber-800/40 rounded-lg px-3 py-2"
                  >
                    <div className="text-xs font-semibold text-amber-300">
                      {b.pattern_name}{" "}
                      <span className="text-amber-500">
                        ×{b.boost_factor.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {b.matched_keywords.map((k) => (
                        <span
                          key={k}
                          className="text-xs bg-amber-900/50 text-amber-200 px-1.5 py-0.5 rounded"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-gray-400 mt-1 italic">
                      {b.note}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Adjusted probability bars */}
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1">
              📊 Xác Suất Sau Hiệu Chỉnh
            </p>
            {insight.adjusted_items.map((item) => (
              <ProbBar key={item.code} item={item} />
            ))}

            {/* Expert summary */}
            {insight.expert_summary && (
              <div className="mt-3 p-3 bg-slate-700/30 rounded-lg border border-slate-600/50">
                <p className="text-xs font-semibold text-emerald-300 mb-1">
                  💡 Nhận Xét Chuyên Gia
                </p>
                <pre className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed font-sans">
                  {insight.expert_summary}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* ── Red flags tab ── */}
        {tab === "redflags" && (
          <div>
            {insight.red_flags.length === 0 ? (
              <div className="text-center py-6">
                <span className="text-2xl">✅</span>
                <p className="text-xs text-gray-400 mt-2">
                  Không phát hiện Red Flag từ triệu chứng hiện tại.
                </p>
              </div>
            ) : (
              <>
                <p className="text-xs text-red-300 mb-2 font-medium">
                  ⚠️ Cần loại trừ khẩn các chẩn đoán nguy hiểm tính mạng:
                </p>
                {insight.red_flags.map((rf, i) => (
                  <RedFlagCard key={`${rf.code}-${i}`} rf={rf} />
                ))}
              </>
            )}
          </div>
        )}

        {/* ── Differential exclusions tab ── */}
        {tab === "exclusions" && (
          <div>
            <p className="text-xs text-slate-400 mb-2 italic">
              Với mỗi chẩn đoán Top-3, Phó GS phản biện: "Nếu là X, tại sao
              không có Y?"
            </p>
            {insight.differential_exclusions.length === 0 ? (
              <p className="text-xs text-gray-500">Không có dữ liệu loại trừ.</p>
            ) : (
              insight.differential_exclusions.map((ex, i) => (
                <ExclusionCard key={`${ex.code}-${i}`} ex={ex} />
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
