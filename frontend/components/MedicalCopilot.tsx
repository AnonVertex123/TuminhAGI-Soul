"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

type Role = "user" | "assistant";
type ChatItem = { role: Role; text: string };

type CopilotProps = {
  diagnosisPayload: any | null;
  criticReasoning: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function sseParseStream(stream: ReadableStream<Uint8Array>, onEvent: (msg: any) => void) {
  const decoder = new TextDecoder("utf-8");
  const reader = stream.getReader();

  let buffer = "";

  return (async () => {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events separated by blank line.
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

        onEvent(msg);
        sepIdx = buffer.indexOf("\n\n");
      }
    }
  })();
}

export default function MedicalCopilot(props: CopilotProps) {
  const [chat, setChat] = useState<ChatItem[]>([
    {
      role: "assistant",
      text: "Chào huynh. Nếu huynh muốn biết: “Tại sao Đao phủ lại từ chối ca bệnh này?”, cứ hỏi thẳng tôi.",
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const contextSummary = useMemo(() => {
    const dp = props.diagnosisPayload || {};
    const critic = props.criticReasoning || "";

    const query = typeof dp.query === "string" ? dp.query : "";
    const status = typeof dp.status === "string" ? dp.status : "";
    const codes = typeof dp.codes === "string" ? dp.codes : "";
    const confidence = dp.confidence;
    const summary = typeof dp.summary === "string" ? dp.summary : "";
    const details = typeof dp.details === "string" ? dp.details : "";

    // Keep it short to avoid extremely large prompts.
    const criticTrim = critic.length > 1400 ? critic.slice(0, 1400) + "..." : critic;
    const summaryTrim = summary.length > 900 ? summary.slice(0, 900) + "..." : summary;
    const detailsTrim = details.length > 1400 ? details.slice(0, 1400) + "..." : details;

    return {
      query,
      status,
      codes,
      confidence,
      summary: summaryTrim,
      details: detailsTrim,
      criticReasoning: criticTrim,
    };
  }, [props.diagnosisPayload, props.criticReasoning]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat, streaming]);

  const send = async () => {
    const message = input.trim();
    if (!message || streaming) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setInput("");
    setStreaming(true);

    setChat((prev) => [...prev, { role: "user", text: message }, { role: "assistant", text: "" }]);

    try {
      const res = await fetch(`${API_BASE}/copilot/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          message,
          context: contextSummary,
        }),
        signal: ctrl.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`copilot/chat failed: ${res.status}`);
      }

      await sseParseStream(res.body, (msg) => {
        if (msg.event === "copilot_token") {
          const token = String(msg.payload?.token ?? "");
          setChat((prev) => {
            const copy = [...prev];
            const lastIdx = copy.length - 1;
            if (copy[lastIdx]?.role !== "assistant") return copy;
            copy[lastIdx] = { ...copy[lastIdx], text: copy[lastIdx].text + token };
            return copy;
          });
        }
        if (msg.event === "copilot_end") {
          setStreaming(false);
        }
        if (msg.event === "copilot_error") {
          const err = String(msg.payload?.error ?? "unknown");
          setChat((prev) => {
            const copy = [...prev];
            const lastIdx = copy.length - 1;
            if (copy[lastIdx]?.role !== "assistant") return copy;
            copy[lastIdx] = { ...copy[lastIdx], text: `Error: ${err}` };
            return copy;
          });
          setStreaming(false);
        }
      });
    } catch (e: any) {
      setChat((prev) => {
        const copy = [...prev];
        const lastIdx = copy.length - 1;
        if (copy[lastIdx]?.role !== "assistant") return copy;
        copy[lastIdx] = { ...copy[lastIdx], text: `Error: ${e?.message || String(e)}` };
        return copy;
      });
      setStreaming(false);
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-emerald-500/20 bg-white/70 dark:bg-gray-900/40 shadow-soft overflow-hidden">
      <div className="px-3 py-2 border-b border-emerald-500/15 flex items-center justify-between">
        <div className="text-[13px] font-semibold text-slate-900 dark:text-slate-100">Medical Copilot</div>
        <div className="text-[11px] text-emerald-700 dark:text-emerald-300">
          Typewriter • Emerald
        </div>
      </div>

      <div className="h-[240px] overflow-y-auto p-3 space-y-2">
        {chat.map((m, idx) => (
          <div key={idx} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={
                m.role === "user"
                  ? "inline-block max-w-[92%] px-3 py-2 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500/30 text-[12px]"
                  : "inline-block max-w-[92%] px-3 py-2 rounded-xl bg-white dark:bg-gray-950 text-slate-800 dark:text-slate-100 ring-1 ring-black/5 dark:ring-white/10 text-[12px]"
              }
            >
              {m.text}
            </div>
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-gray-950/20">
        <div className="flex gap-2 items-center">
          <input
            value={input}
            disabled={streaming}
            onChange={(e) => setInput(e.target.value)}
            className="flex-1 h-[34px] rounded-xl px-3 bg-white dark:bg-gray-950 text-[13px] outline-none ring-1 ring-black/5 dark:ring-white/10 disabled:opacity-60"
            placeholder={streaming ? "Đang trợ lý..." : "Hỏi trợ lý Tự Minh..."}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="button"
            disabled={streaming}
            onClick={() => void send()}
            className="h-[34px] px-4 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-[13px] font-medium shadow-soft disabled:opacity-60"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

