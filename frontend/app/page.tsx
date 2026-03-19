"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import MedicalCopilot from "../components/MedicalCopilot";
import ExpertInsights, { type ExpertInsightPayload } from "../components/ExpertInsights";
import StructuredOutputPanel, { type StructuredOutputData } from "../components/StructuredOutputPanel";

type ThemeMode = "light" | "dark";

type TimelineStepId = "chapter" | "reverse" | "critic" | "final";
type TimelineStepContents = Record<TimelineStepId, string>;
type ChatMessage = { who: "patient" | "agent"; text: string };

type DiffItem = { code: string; description: string; prob: number };
type DiffQuestion = {
  id: string;
  label: string;
  effects: { yes: Record<string, number>; no: Record<string, number> };
};

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function renormalize(items: DiffItem[]): DiffItem[] {
  const s = items.reduce((acc, it) => acc + (Number.isFinite(it.prob) ? it.prob : 0), 0);
  if (s <= 0.0001) return items.map((it) => ({ ...it, prob: 0 }));
  return items.map((it) => ({ ...it, prob: clamp((it.prob / s) * 100, 0, 100) }));
}

function applyDiffAnswer(items: DiffItem[], q: DiffQuestion, ans: "yes" | "no"): DiffItem[] {
  const effects = q.effects?.[ans] || {};
  const next = items.map((it) => {
    const mult = typeof effects[it.code] === "number" ? effects[it.code] : 1.0;
    return { ...it, prob: clamp(it.prob * mult, 0, 100) };
  });
  return renormalize(next);
}

function DifferentialChecklist(props: {
  items: DiffItem[];
  questions: DiffQuestion[];
  onAnswer: (q: DiffQuestion, ans: "yes" | "no") => void;
}) {
  return (
    <div className="mt-4 rounded-xl bg-white dark:bg-gray-900 shadow-soft ring-1 ring-black/5 dark:ring-white/10 overflow-hidden">
      <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="text-[13px] font-semibold">Chẩn đoán phân biệt</div>
        <div className="text-[11px] text-slate-500 dark:text-slate-400">Realtime %</div>
      </div>

      <div className="p-3 space-y-3">
        {props.items.length === 0 ? (
          <div className="text-[12px] text-slate-500 dark:text-slate-400">
            Chưa có danh sách nghi ngờ. Hãy chạy chẩn đoán để hệ thống stream sang.
          </div>
        ) : (
          props.items.map((it) => (
            <div key={it.code} className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[12px] font-medium text-slate-900 dark:text-slate-100 truncate">
                  {it.code} — {it.description}
                </div>
                <div className="text-[12px] font-semibold text-emerald-700 dark:text-emerald-300 shrink-0">
                  {Math.round(it.prob)}%
                </div>
              </div>
              <div className="h-[8px] rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden ring-1 ring-black/5 dark:ring-white/10">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${clamp(it.prob, 0, 100)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {props.questions.length > 0 ? (
        <div className="px-3 pb-3">
          <div className="text-[12px] font-semibold text-slate-900 dark:text-slate-100 mb-2">
            Gợi ý câu hỏi
          </div>
          <div className="space-y-2">
            {props.questions.map((q) => (
              <div
                key={q.id}
                className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-gray-950/20 p-2"
              >
                <div className="text-[12px] text-slate-700 dark:text-slate-200 leading-relaxed">
                  {q.label}
                </div>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => props.onAnswer(q, "yes")}
                    className="h-[28px] px-3 rounded-lg text-[12px] font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500/30 hover:bg-emerald-500/15"
                  >
                    Có
                  </button>
                  <button
                    type="button"
                    onClick={() => props.onAnswer(q, "no")}
                    className="h-[28px] px-3 rounded-lg text-[12px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-1 ring-amber-500/30 hover:bg-amber-500/15"
                  >
                    Không
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function IconPlus(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function IconCheck(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function IconSearch(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M21 21l-4.35-4.35" />
      <circle cx="11" cy="11" r="7" />
    </svg>
  );
}

function IconLeaf(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M21 3c-8 1-14 7-15 15 8-1 14-7 15-15Z" />
      <path d="M9 15c0-3 3-6 6-6" />
    </svg>
  );
}

function IconScale(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M12 3v18" />
      <path d="M7 7l5-4 5 4" />
      <path d="M5 21h14" />
      <path d="M7 7l-2 4h4l-2-4Z" />
      <path d="M17 7l-2 4h4l-2-4Z" />
    </svg>
  );
}

function IconSun(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M4.93 4.93l1.41 1.41" />
      <path d="M17.66 17.66l1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M4.93 19.07l1.41-1.41" />
      <path d="M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function IconMoon(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

function classNames(...xs: Array<string | undefined | false>) {
  return xs.filter(Boolean).join(" ");
}

function ReasoningTimeline(props: {
  executionMode: boolean;
  stepContents: TimelineStepContents;
  criticMeta?: { status: string; confidence?: number } | null;
}) {
  const steps = useMemo(
    () => [
      {
        id: "chapter",
        title: "Chapter Guard",
        content:
          "Kiểm tra tính nhất quán của Chương ICD (Vietnamese/English symptom group) trước khi chốt mã."
      },
      {
        id: "reverse",
        title: "Reverse Description Check",
        content:
          "Đối chiếu mô tả ngược từ mã ICD sang triệu chứng người dùng (core diagnosis match)."
      },
      {
        id: "critic",
        title: "Critic Layer (Đao phủ)",
        content: props.executionMode
          ? "Partial/Core match + phạt các mâu thuẫn logic rõ ràng giữa triệu chứng và ICD."
          : "Đang ở chế độ thường: có audit nhẹ thay vì phản biện nặng."
      },
      {
        id: "final",
        title: "Final Validation",
        content: "Chốt kết quả cuối + ghi lịch sử suy luận để truy vết."
      }
    ],
    [props.executionMode]
  );

  const [open, setOpen] = useState<Record<TimelineStepId, boolean>>({
    chapter: true,
    reverse: false,
    critic: false,
    final: false
  });

  useEffect(() => {
    // Auto-expand a step once we have streamed content for it.
    setOpen((prev) => {
      const next = { ...prev };
      (["chapter", "reverse", "critic", "final"] as TimelineStepId[]).forEach((k) => {
        if (props.stepContents[k] && !next[k]) next[k] = true;
      });
      return next;
    });
  }, [props.stepContents]);

  return (
    <div className="space-y-3">
      {steps.map((s) => {
        const isOpen = !!open[s.id as TimelineStepId];
        const override = props.stepContents[s.id as TimelineStepId];

        const criticBadge =
          s.id === "critic" && props.criticMeta ? (
            (() => {
              const status = (props.criticMeta?.status || "").toUpperCase();
              const conf = props.criticMeta?.confidence;
              const confStr = typeof conf === "number" ? `${Math.round(conf)}%` : "";

              if (status === "APPROVED") {
                return (
                  <div className="mb-2 text-[11px] px-2 py-1 rounded-md font-medium ring-1 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/30">
                    Tin cậy: {confStr || "—"} (APPROVED)
                  </div>
                );
              }

              // SUGGESTION => Amber (thay vì đỏ)
              if (status === "SUGGESTION") {
                return (
                  <div className="mb-2 text-[11px] px-2 py-1 rounded-md font-medium ring-1 bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/30">
                    Tin cậy: {confStr || "—"} (SUGGESTION)
                  </div>
                );
              }

              // REJECTED => Red
              return (
                <div className="mb-2 text-[11px] px-2 py-1 rounded-md font-medium ring-1 bg-rose-500/10 text-rose-700 dark:text-rose-300 ring-rose-500/30">
                  Tin cậy: {confStr || "—"} (REJECTED)
                </div>
              );
            })()
          ) : null;

        return (
          <div
            key={s.id}
            className="rounded-xl bg-white dark:bg-gray-900 shadow-soft ring-1 ring-black/5 dark:ring-white/10"
          >
            <button
              type="button"
              onClick={() =>
                setOpen((m) => ({
                  ...m,
                  [s.id]: !m[s.id as TimelineStepId]
                }))
              }
              className="w-full flex items-center justify-between px-3 py-3"
            >
              <div className="text-[13px] font-medium text-slate-900 dark:text-slate-100 text-left">
                {s.title}
              </div>
              <div className="text-slate-500 dark:text-slate-400 text-[12px]">
                {isOpen ? "−" : "+"}
              </div>
            </button>
            {isOpen ? (
              <div className="px-3 pb-3 text-[12px] text-slate-600 dark:text-slate-300 leading-relaxed">
                {criticBadge}
                {override || s.content}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function CommandPaletteOverlay(props: {
  isOpen: boolean;
  onClose: () => void;
  theme: ThemeMode;
  onToggleTheme: () => void;
  executionMode: boolean;
  onToggleExecutionMode: () => void;
  onNewDiagnosis: () => void;
  onEndSession: () => void;
  onNavigateIcD: () => void;
  onNavigateThuoc: () => void;
}) {
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (props.isOpen) {
      setQ("");
      const t = window.setTimeout(() => inputRef.current?.focus(), 60);
      return () => window.clearTimeout(t);
    }
  }, [props.isOpen]);

  useEffect(() => {
    if (!props.isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") props.onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [props.isOpen, props.onClose]);

  const sections = useMemo(() => {
    const norm = q.trim().toLowerCase();
    const match = (s: string) => (norm ? s.toLowerCase().includes(norm) : true);

    const base = [
      {
        title: "HÀNH ĐỘNG",
        items: [
          {
            id: "new",
            label: "Chẩn đoán ca mới",
            icon: <IconPlus className="w-[16px] h-[16px]" />,
            onRun: props.onNewDiagnosis
          },
          {
            id: "end",
            label: "Kết thúc phiên khám",
            icon: <IconCheck className="w-[16px] h-[16px]" />,
            onRun: props.onEndSession
          }
        ]
      },
      {
        title: "TRA CỨU",
        items: [
          {
            id: "icd",
            label: "/icd",
            icon: <IconSearch className="w-[16px] h-[16px]" />,
            onRun: props.onNavigateIcD
          },
          {
            id: "thuoc",
            label: "/thuoc",
            icon: <IconLeaf className="w-[16px] h-[16px]" />,
            onRun: props.onNavigateThuoc
          }
        ]
      },
      {
        title: "CÀI ĐẶT HỆ THỐNG",
        items: [
          {
            id: "mode",
            label: "Chế độ Đao phủ [Bật/Tắt]",
            icon: <IconScale className="w-[16px] h-[16px]" />,
            onRun: props.onToggleExecutionMode
          },
          {
            id: "theme",
            label: "Theme: Sáng/Tối",
            icon:
              props.theme === "dark" ? (
                <IconSun className="w-[16px] h-[16px]" />
              ) : (
                <IconMoon className="w-[16px] h-[16px]" />
              ),
            onRun: props.onToggleTheme
          }
        ]
      }
    ];

    return base
      .map((sec) => ({
        ...sec,
        items: sec.items.filter((it) => match(it.label))
      }))
      .filter((sec) => sec.items.length > 0);
  }, [
    q,
    props.onEndSession,
    props.onNewDiagnosis,
    props.onNavigateIcD,
    props.onNavigateThuoc,
    props.onToggleExecutionMode,
    props.onToggleTheme,
    props.theme
  ]);

  if (!props.isOpen) return null;

  return (
    <div className="fixed inset-0 z-[80]">
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/50"
        onMouseDown={props.onClose}
      />

      <div className="absolute inset-0 pointer-events-none">
        <div
          className={classNames(
            "pointer-events-auto",
            "absolute top-[56px] right-4 bottom-4",
            "w-[480px] max-w-[92vw] max-h-[70vh]",
            "rounded-xl bg-white dark:bg-gray-900",
            "shadow-lg ring-1 ring-black/5 dark:ring-white/10",
            "overflow-hidden"
          )}
          role="dialog"
          aria-modal="true"
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Input row */}
          <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-gray-900/90">
            <div className="flex items-center gap-[10px]">
              <span className="text-slate-500 dark:text-slate-300">
                <IconSearch className="w-[16px] h-[16px]" />
              </span>
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search, run a command, or ask a question..."
                className="w-full bg-transparent outline-none text-[13px] text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
              />
            </div>
          </div>

          {/* Results */}
          <div className="overflow-y-auto max-h-[calc(70vh-48px)] px-1 py-2">
            {sections.map((sec, idx) => (
              <div key={sec.title} className={idx === 0 ? "" : "mt-2"}>
                <div className="text-[11px] font-medium tracking-wide text-slate-500 dark:text-slate-400 px-3 pt-[6px] pb-[2px]">
                  {sec.title}
                </div>

                <div className="space-y-1">
                  {sec.items.map((it) => (
                    <button
                      key={it.id}
                      type="button"
                      onClick={() => {
                        it.onRun();
                        props.onClose();
                      }}
                      className="w-full h-[34px] px-3 flex items-center gap-[10px] rounded-md text-[13px] cursor-pointer
                                 hover:bg-slate-100 dark:hover:bg-gray-800
                                 active:bg-slate-200/70 dark:active:bg-gray-700
                                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/70"
                    >
                      <span className="w-[16px] h-[16px] shrink-0 text-slate-600 dark:text-slate-300 flex items-center justify-center">
                        {it.icon}
                      </span>
                      <span className="truncate text-slate-900 dark:text-slate-100 text-left">
                        {it.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}

            {sections.length === 0 ? (
              <div className="px-3 py-6 text-[13px] text-slate-600 dark:text-slate-300">
                No results.
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [executionMode, setExecutionMode] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [symptomsInput, setSymptomsInput] = useState("");
  const [diagnosing, setDiagnosing] = useState(false);

  const API_BASE = "http://localhost:8000";

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      who: "patient",
      text: "Tôi bị ho kéo dài kèm sốt nhẹ về chiều."
    },
    {
      who: "agent",
      text: "Mình đã dịch triệu chứng sang English, sau đó đối chiếu chương ICD và thực hiện audit Đao phủ."
    }
  ]);

  const [timeline, setTimeline] = useState<TimelineStepContents>({
    chapter: "",
    reverse: "",
    critic: "",
    final: ""
  });

  const [latestDiagnosisPayload, setLatestDiagnosisPayload] = useState<any | null>(null);

  const [criticMeta, setCriticMeta] = useState<{
    status: string;
    confidence?: number;
  } | null>(null);

  const [diffItems, setDiffItems] = useState<DiffItem[]>([]);
  const [diffQuestions, setDiffQuestions] = useState<DiffQuestion[]>([]);
  const [expertInsights, setExpertInsights] = useState<ExpertInsightPayload | null>(null);
  const [structuredOutput, setStructuredOutput] = useState<StructuredOutputData | null>(null);

  // Critic typewriter: buffer tokens and render at fixed cadence.
  const criticQueueRef = useRef<string[]>([]);
  const criticDoneRef = useRef(false);
  const criticTimerRef = useRef<number | null>(null);

  const stopCriticTimer = () => {
    if (criticTimerRef.current !== null) {
      window.clearInterval(criticTimerRef.current);
      criticTimerRef.current = null;
    }
  };

  const startCriticTimerIfNeeded = () => {
    if (criticTimerRef.current !== null) return;
    criticTimerRef.current = window.setInterval(() => {
      const q = criticQueueRef.current;
      if (q.length > 0) {
        const next = q.shift() ?? "";
        setTimeline((prev) => ({ ...prev, critic: prev.critic + next }));
        return;
      }
      if (criticDoneRef.current) {
        stopCriticTimer();
      }
    }, 18);
  };

  useEffect(() => {
    return () => {
      stopCriticTimer();
    };
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("tuminh_theme");
    const initial: ThemeMode =
      stored === "dark" || stored === "light" ? (stored as ThemeMode) : "light";
    setTheme(initial);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("tuminh_theme", theme);
  }, [theme]);

  const resetTimeline = () => {
    criticQueueRef.current = [];
    criticDoneRef.current = false;
    stopCriticTimer();
    setTimeline({
      chapter: "",
      reverse: "",
      critic: "",
      final: ""
    });
    setStructuredOutput(null);
  };

  const appendTimeline = (step: TimelineStepId, line: string) => {
    setTimeline((prev) => ({
      ...prev,
      [step]: prev[step] ? `${prev[step]}\n${line}` : line
    }));
  };

  const postCommand = async (type: string, payload?: any) => {
    await fetch(`${API_BASE}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, payload })
    });
  };

  const handleNewDiagnosis = async () => {
    await postCommand("new_diagnosis");
  };

  const handleEndSession = async () => {
    await postCommand("end_session");
  };

  const handleNavigateIcD = async () => {
    await postCommand("navigate_icd");
  };

  const handleNavigateThuoc = async () => {
    await postCommand("navigate_thuoc");
  };

  const handleToggleExecutionMode = async () => {
    const next = !executionMode;
    setExecutionMode(next);
    try {
      await postCommand("toggle_execution_mode", { value: next });
    } catch {
      // ignore
    }
  };

  const handleToggleTheme = async () => {
    const next: ThemeMode = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      await postCommand("toggle_theme", { value: next });
    } catch {
      // ignore
    }
  };

  const abortRef = useRef<AbortController | null>(null);

  const streamDiagnose = async (userQuery: string) => {
    // Cancel any in-flight request
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    resetTimeline();
    setDiagnosing(true);
    setDiffItems([]);
    setDiffQuestions([]);
    setExpertInsights(null);

    setMessages((prev) => [
      ...prev,
      { who: "patient", text: userQuery },
      { who: "agent", text: "Đang xử lý... (streaming reasoning)" }
    ]);

    const applyFinal = (payload: any) => {
      setTimeline((prev) => ({
        ...prev,
        final: payload.summary || prev.final
      }));
      setLatestDiagnosisPayload(payload || null);
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const copy = [...prev];
        const lastIdx = copy.length - 1;
        if (copy[lastIdx]?.who === "agent") {
          copy[lastIdx] = {
            who: "agent",
            text: payload.details || payload.summary
          };
        }
        return copy;
      });
    };

    try {
      // Backend stream endpoint: MUST be exactly `/diagnose/stream` (no trailing slash).
      const url = `http://localhost:8000/diagnose/stream?query=${encodeURIComponent(
        userQuery
      )}&executionMode=${executionMode}`;

      const res = await fetch(url, {
        method: "GET",
        headers: { Accept: "text/event-stream" },
        signal: ctrl.signal
      });

      if (!res.ok || !res.body) {
        throw new Error(`diagnose_stream failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by a blank line
        let sepIdx = buffer.indexOf("\n\n");
        while (sepIdx !== -1) {
          const rawEvent = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);

          const dataLines = rawEvent
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trim());

          if (dataLines.length === 0) {
            sepIdx = buffer.indexOf("\n\n");
            continue;
          }

          const dataStr = dataLines.join("\n");
          let msg: any;
          try {
            msg = JSON.parse(dataStr);
          } catch {
            sepIdx = buffer.indexOf("\n\n");
            continue;
          }

          if (msg.event === "critic_start") {
            criticQueueRef.current = [];
            criticDoneRef.current = false;
            stopCriticTimer();
            setCriticMeta(null);
            setTimeline((prev) => ({
              ...prev,
              critic: prev.critic ? prev.critic + "\n" : ""
            }));
          } else if (msg.event === "critic_end") {
            criticDoneRef.current = true;
            startCriticTimerIfNeeded();
          } else if (msg.event === "critic_meta") {
            const status = String(msg.payload?.status ?? "");
            const confidence = msg.payload?.confidence;
            if (status) {
              setCriticMeta({ status, confidence: typeof confidence === "number" ? confidence : undefined });
            }
          } else if (msg.event === "critic_token") {
            const token = String(msg.payload?.token ?? "");
            criticQueueRef.current.push(token);
            startCriticTimerIfNeeded();
          } else if (msg.event === "timeline_log") {
            const step = msg.step as TimelineStepId;
            if (step && step !== "critic") appendTimeline(step, msg.message);
          } else if (msg.event === "final") {
            applyFinal(msg.payload);
          } else if (msg.event === "diff_update") {
            const items = Array.isArray(msg.payload?.items) ? msg.payload.items : [];
            const parsed: DiffItem[] = items
              .map((x: any) => ({
                code: String(x.code ?? ""),
                description: String(x.description ?? ""),
                prob: Number(x.prob ?? 0),
              }))
              .filter((x: DiffItem) => x.code);
            setDiffItems(renormalize(parsed));
          } else if (msg.event === "diff_questions") {
            const qs = Array.isArray(msg.payload?.questions) ? msg.payload.questions : [];
            const parsed: DiffQuestion[] = qs
              .map((q: any) => ({
                id: String(q.id ?? ""),
                label: String(q.label ?? ""),
                effects: q.effects || { yes: {}, no: {} },
              }))
              .filter((q: DiffQuestion) => q.id && q.label);
            setDiffQuestions(parsed);
          } else if (msg.event === "expert_insights") {
            const p = msg.payload;
            if (p && Array.isArray(p.adjusted_items)) {
              setExpertInsights(p as ExpertInsightPayload);
            }
          } else if (msg.event === "structured_output") {
            if (msg.payload) {
              setStructuredOutput(msg.payload as StructuredOutputData);
            }
          } else if (msg.event === "error") {
            appendTimeline("final", `Error: ${msg.payload?.error || "unknown"}`);
          }

          sepIdx = buffer.indexOf("\n\n");
        }
      }
    } catch (e: any) {
      appendTimeline("final", `Error: ${e?.message || String(e)}`);
    } finally {
      setDiagnosing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] dark:bg-gray-950 text-slate-900 dark:text-slate-100">
      {/* Header */}
      <div className="h-[56px] flex items-center justify-between px-4 border-b border-slate-200 dark:border-slate-800 bg-[#f8fafc] dark:bg-gray-950">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white dark:bg-gray-900 shadow-soft ring-1 ring-black/5 dark:ring-white/10 flex items-center justify-center font-semibold">
            TM
          </div>
          <div className="leading-tight">
            <div className="text-[14px] font-semibold">Tự Minh AGI</div>
            <div className="text-[12px] text-slate-500 dark:text-slate-400">
              Medical Diagnostic Dashboard
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsSearchOpen((v) => !v)}
            aria-label="Open search"
            className="w-[36px] h-[36px] rounded-md hover:bg-slate-100 dark:hover:bg-gray-800
                       flex items-center justify-center text-slate-700 dark:text-slate-200 ring-1 ring-black/5 dark:ring-white/10"
          >
            <IconSearch className="w-[18px] h-[18px]" />
          </button>
        </div>
      </div>

      {/* Main 3-column layout */}
      <div className="flex h-[calc(100vh-56px)] overflow-hidden">
        {/* Sidebar (260px fixed) */}
        <aside className="w-[260px] shrink-0 border-r border-slate-200 dark:border-slate-800 bg-[#f8fafc] dark:bg-gray-950 overflow-y-auto">
          <div className="p-3">
            <div className="text-[12px] font-medium text-slate-500 dark:text-slate-400 mb-2">
              Patient / Cases
            </div>
            <div className="space-y-2">
              {Array.from({ length: 12 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-xl bg-white dark:bg-gray-900 shadow-soft ring-1 ring-black/5 dark:ring-white/10 p-3"
                >
                  <div className="text-[13px] font-medium text-slate-900 dark:text-slate-100">
                    Case #{i + 1}
                  </div>
                  <div className="text-[12px] text-slate-500 dark:text-slate-400 mt-1">
                    Recent summary...
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Chat panel (flex) */}
        <main className="flex-1 overflow-hidden bg-[#f8fafc] dark:bg-gray-950">
          <div className="h-full flex flex-col">
            {/* Chat scroll area */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-[900px] mx-auto space-y-3">
                {messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={classNames(
                      "rounded-xl shadow-soft ring-1 ring-black/5 dark:ring-white/10 p-3",
                      m.who === "patient"
                        ? "bg-white dark:bg-gray-900"
                        : "bg-emerald-50/60 dark:bg-emerald-900/20"
                    )}
                  >
                    <div className="text-[12px] font-medium text-slate-500 dark:text-slate-400 mb-1">
                      {m.who === "patient" ? "Patient" : "Tự Minh AGI"}
                    </div>
                    <div className="text-[13px] text-slate-900 dark:text-slate-100 leading-relaxed">
                      {m.text}
                    </div>
                  </div>
                ))}

                {/* ── Structured Output V2.0 ── */}
                {structuredOutput && (
                  <div className="rounded-2xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/20 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm">🤖</span>
                      <span className="text-[12px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
                        Tự Minh AGI — Thông tin hỗ trợ
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 dark:text-slate-500 mb-2">
                      Thông tin dưới đây chỉ mang tính tham khảo, không phải chẩn đoán y tế chính thức.
                    </p>
                    <StructuredOutputPanel data={structuredOutput} />
                  </div>
                )}
              </div>
            </div>

            {/* Chat composer */}
            <div className="border-t border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-gray-900/40 backdrop-blur">
              <div className="max-w-[900px] mx-auto p-3 flex items-center gap-2">
                <input
                  value={symptomsInput}
                  disabled={diagnosing}
                  onChange={(e) => setSymptomsInput(e.target.value)}
                  className="flex-1 h-[38px] rounded-xl px-3 bg-white dark:bg-gray-950/60
                             text-[13px] outline-none ring-1 ring-black/5 dark:ring-white/10 disabled:opacity-60"
                  placeholder={diagnosing ? "Đang chẩn đoán..." : "Nhập triệu chứng (VN)..."}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void (async () => {
                        const t = symptomsInput.trim();
                        if (!t || diagnosing) return;
                        await streamDiagnose(t);
                        setSymptomsInput("");
                      })();
                    }
                  }}
                />
                <button
                  type="button"
                  disabled={diagnosing}
                  className="h-[38px] px-4 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-[13px] font-medium shadow-soft"
                  style={{ opacity: diagnosing ? 0.7 : 1 }}
                  onClick={() => {
                    void (async () => {
                      const t = symptomsInput.trim();
                      if (!t || diagnosing) return;
                      await streamDiagnose(t);
                      setSymptomsInput("");
                    })();
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </main>

        {/* Reasoning panel (380px fixed) */}
        <aside className="w-[380px] shrink-0 border-l border-slate-200 dark:border-slate-800 bg-[#f8fafc] dark:bg-gray-950 overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[14px] font-semibold">Diagnostic Reasoning</div>
                <div className="text-[12px] text-slate-500 dark:text-slate-400 mt-1">
                  Đao phủ & kiểm toán chuỗi suy luận
                </div>
              </div>
              <div
                className={classNames(
                  "text-[11px] px-2 py-1 rounded-md font-medium ring-1",
                  executionMode
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/30"
                    : "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/30"
                )}
              >
                {executionMode ? "Đao phủ: ON" : "Đao phủ: OFF"}
              </div>
            </div>

            <ReasoningTimeline
              executionMode={executionMode}
              stepContents={timeline}
              criticMeta={criticMeta}
            />

            <DifferentialChecklist
              items={diffItems}
              questions={diffQuestions}
              onAnswer={(q, ans) => {
                setDiffItems((prev) => applyDiffAnswer(prev, q, ans));
              }}
            />

            {/* Clinical Reasoning Engine — PGS Expert Insights */}
            <div className="mt-4">
              <ExpertInsights insight={expertInsights} />
            </div>

            {/* Copilot mini-chat sits under the reasoning timeline */}
            <MedicalCopilot
              diagnosisPayload={latestDiagnosisPayload}
              criticReasoning={timeline.critic}
            />
          </div>
        </aside>
      </div>

      {/* Search overlay toggle right dock */}
      <CommandPaletteOverlay
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        theme={theme}
        onToggleTheme={() => {
          void handleToggleTheme();
        }}
        executionMode={executionMode}
        onToggleExecutionMode={() => {
          void handleToggleExecutionMode();
        }}
        onNewDiagnosis={() => {
          void handleNewDiagnosis();
        }}
        onEndSession={() => {
          void handleEndSession();
        }}
        onNavigateIcD={() => {
          void handleNavigateIcD();
        }}
        onNavigateThuoc={() => {
          void handleNavigateThuoc();
        }}
      />
    </div>
  );
}

