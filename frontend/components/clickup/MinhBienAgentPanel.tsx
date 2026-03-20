"use client";

import React, { useMemo, useState, useRef, useEffect } from "react";
import {
  Paperclip,
  MoreHorizontal,
  Search,
  UserPlus,
  PenLine,
} from "lucide-react";
import type { ModuleId } from "./moduleConfig";
import ExpertInsights, { type ExpertInsightPayload } from "../ExpertInsights";
import StructuredOutputPanel, { type StructuredOutputData } from "../StructuredOutputPanel";
import EmergencyResponsePanel from "../EmergencyResponsePanel";

export type ChatMsg = {
  id: string;
  who: "agent" | "user";
  text: string;
  ts: string;
  replies?: number;
};

const DEFAULT_SUGGESTIONS: { title: string; items: { label: string; badge?: string }[] }[] = [
  { title: "Gợi ý", items: [{ label: "Tôi có thể giúp gì cho bạn?" }] },
];

const SUGGESTIONS_BY_MODULE: Record<
  ModuleId,
  { title: string; items: { label: string; badge?: string }[] }[]
> = {
  home: [
    { title: "Gợi ý", items: [{ label: "Chọn module để bắt đầu" }] },
  ],
  y_hoc: [
    {
      title: "Gợi ý",
      items: [
        { label: "Giải thích triệu chứng vừa nhập" },
        { label: "Xem lịch sử bệnh nhân" },
        { label: "Tóm tắt phác đồ điều trị" },
      ],
    },
    {
      title: "Nổi bật",
      items: [
        { label: "Chẩn đoán nhanh", badge: "Mới" },
        { label: "Tạo báo cáo", badge: "Mới" },
        { label: "Hỏi về thuốc Nam", badge: "Mới" },
      ],
    },
    {
      title: "Tìm kiếm",
      items: [
        { label: "Tìm trong Tự Minh" },
        { label: "Tìm y văn PubMed" },
        { label: "Tìm thuốc Nam" },
      ],
    },
    {
      title: "Báo cáo",
      items: [
        { label: "Tổng kết ca hôm nay" },
        { label: "Báo cáo tuần" },
        { label: "Phác đồ điều trị" },
      ],
    },
    {
      title: "Tạo & Viết",
      items: [
        { label: "Tạo hồ sơ bệnh nhân" },
        { label: "Viết tóm tắt" },
        { label: "Brainstorm" },
      ],
    },
  ],
  code: [
    {
      title: "Gợi ý",
      items: [
        { label: "Giải thích đoạn code" },
        { label: "Tối ưu hiệu năng" },
        { label: "Viết unit test" },
      ],
    },
    {
      title: "Nổi bật",
      items: [
        { label: "Code review", badge: "Mới" },
        { label: "Refactor", badge: "Mới" },
      ],
    },
  ],
  hoc_tap: [
    {
      title: "Gợi ý",
      items: [
        { label: "Tóm tắt tài liệu" },
        { label: "Tạo flashcard" },
        { label: "Ôn tập theo chủ đề" },
      ],
    },
  ],
  du_lieu: [
    {
      title: "Gợi ý",
      items: [
        { label: "Phân tích dữ liệu" },
        { label: "Tạo biểu đồ" },
        { label: "Xuất báo cáo" },
      ],
    },
  ],
  cong_dong: [
    {
      title: "Gợi ý",
      items: [
        { label: "Thảo luận" },
        { label: "Chia sẻ kinh nghiệm" },
      ],
    },
  ],
  nghien_cuu: DEFAULT_SUGGESTIONS,
  minh_bien: DEFAULT_SUGGESTIONS,
  tu_dong: DEFAULT_SUGGESTIONS,
  workspace: DEFAULT_SUGGESTIONS,
  ghi_chu: DEFAULT_SUGGESTIONS,
  muc_tieu: DEFAULT_SUGGESTIONS,
  thoi_gian: DEFAULT_SUGGESTIONS,
};


export default function MinhBienAgentPanel({
  activeModule,
  isEmergency,
  emergencyReason,
  structuredOutput,
  expertInsights,
  messages: externalMessages,
  onSend,
  onDiagnose,
  diagnosisSummary,
  onSuggestionClick,
  className = "",
}: {
  activeModule: ModuleId;
  isEmergency: boolean;
  emergencyReason?: string;
  /** Kết quả /diagnose/v2 (dòng text), hiển thị trong panel cấp cứu */
  diagnosisSummary?: string | null;
  structuredOutput: StructuredOutputData | null;
  expertInsights: ExpertInsightPayload | null;
  messages?: ChatMsg[];
  onSend?: (text: string) => void;
  /** Chuẩn: gọi API + detect — trả về để append tin nhắn agent khi không cấp cứu */
  onDiagnose?: (text: string) => Promise<{
    isEmergency: boolean;
    agentReply: string;
  } | void>;
  onSuggestionClick?: (label: string) => void;
  className?: string;
}) {
  const [input, setInput] = useState("");
  const [tab, setTab] = useState<"chat" | "assigned">("chat");
  const [messages, setMessages] = useState<ChatMsg[]>(
    externalMessages ?? [
      {
        id: "welcome",
        who: "agent",
        text: "Xin chào! Tôi là Tự Minh. Tôi có thể giúp gì cho bạn?",
        ts: new Date().toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]
  );
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (externalMessages?.length) setMessages(externalMessages);
  }, [externalMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, typing]);

  const suggestions = useMemo(
    () =>
      SUGGESTIONS_BY_MODULE[activeModule] ?? DEFAULT_SUGGESTIONS,
    [activeModule]
  );

  const handleSend = async () => {
    const t = input.trim();
    if (!t) return;
    setInput("");
    const userMsg: ChatMsg = {
      id: `u-${Date.now()}`,
      who: "user",
      text: t,
      ts: new Date().toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setTyping(true);

    if (onDiagnose) {
      try {
        const out = await onDiagnose(t);
        setTyping(false);
        if (out && !out.isEmergency && out.agentReply) {
          setMessages((prev) => [
            ...prev,
            {
              id: `a-${Date.now()}`,
              who: "agent",
              text: out.agentReply,
              ts: new Date().toLocaleTimeString("vi-VN", {
                hour: "2-digit",
                minute: "2-digit",
              }),
            },
          ]);
        }
      } catch {
        setTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            who: "agent",
            text: "Lỗi khi gọi chẩn đoán. Kiểm tra API (port 8000) hoặc thử lại.",
            ts: new Date().toLocaleTimeString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
            }),
          },
        ]);
      }
      return;
    }

    onSend?.(t);
    setTimeout(() => {
      setTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          who: "agent",
          text: "Tôi đã nhận được tin nhắn của bạn. Tính năng streaming sẽ được kết nối với /diagnose/stream.",
          ts: new Date().toLocaleTimeString("vi-VN", {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    }, 800);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  if (isEmergency) {
    return (
      <EmergencyResponsePanel
        emergencyReason={emergencyReason}
        diagnosisSummary={diagnosisSummary}
        className={className}
      />
    );
  }

  return (
    <div
      className={`flex flex-col h-full bg-[#FFFFFF] border-l border-[#E8E8F0] overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="shrink-0 px-3 py-2 border-b border-[#E8E8F0] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-[32px] h-[32px] rounded-full bg-[#E1F5EE] flex items-center justify-center shrink-0"
            aria-hidden
          >
            🌿
          </div>
          <span className="text-[13px] font-bold text-[#1B1B2F] truncate">
            Tự Minh
          </span>
          <button
            type="button"
            aria-label="Menu"
            className="p-1 rounded hover:bg-[#F5F5FA] text-[#6B6B8A]"
          >
            <MoreHorizontal className="w-[16px] h-[16px]" />
          </button>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            className="p-1.5 rounded-lg hover:bg-[#F5F5FA] text-[#6B6B8A]"
            aria-label="Search"
          >
            <Search className="w-[16px] h-[16px]" />
          </button>
          <button
            type="button"
            className="p-1.5 rounded-lg hover:bg-[#F5F5FA] text-[#6B6B8A]"
            aria-label="Assigned"
          >
            <UserPlus className="w-[16px] h-[16px]" />
          </button>
          <button
            type="button"
            className="p-1.5 rounded-lg hover:bg-[#F5F5FA] text-[#6B6B8A]"
            aria-label="Edit"
          >
            <PenLine className="w-[16px] h-[16px]" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="shrink-0 flex border-b border-[#E8E8F0]">
        <button
          type="button"
          onClick={() => setTab("chat")}
          className={`flex-1 py-2 text-[12px] font-semibold transition-colors ${
            tab === "chat"
              ? "text-[#7B68EE] border-b-2 border-[#7B68EE]"
              : "text-[#6B6B8A] hover:text-[#1B1B2F]"
          }`}
        >
          Chat
        </button>
        <button
          type="button"
          onClick={() => setTab("assigned")}
          className={`flex-1 py-2 text-[12px] font-semibold transition-colors ${
            tab === "assigned"
              ? "text-[#7B68EE] border-b-2 border-[#7B68EE]"
              : "text-[#6B6B8A] hover:text-[#1B1B2F]"
          }`}
        >
          Nhiệm vụ được giao
        </button>
      </div>

      {/* Content */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 min-h-0">
        {tab === "chat" ? (
          <>
            {messages.length === 1 && messages[0]?.who === "agent" ? (
              <div className="space-y-4">
                <div className="rounded-xl bg-[#F8F8FC] ring-1 ring-black/5 p-4">
                  <div className="text-[14px] font-semibold text-[#1B1B2F] mb-1">
                    🌿 Xin chào!
                  </div>
                  <div className="text-[13px] text-[#6B6B8A]">
                    Tôi là Tự Minh. Tôi có thể giúp gì cho bạn?
                  </div>
                </div>
                {suggestions.map((sec) => (
                  <div key={sec.title}>
                    <div className="text-[11px] font-semibold text-[#6B6B8A] uppercase tracking-wide mb-2">
                      {sec.title}
                    </div>
                    <div className="space-y-1">
                      {sec.items.map((item) => (
                        <button
                          key={item.label}
                          type="button"
                          onClick={() => {
                            onSuggestionClick?.(item.label);
                            setInput(item.label);
                          }}
                          className="w-full text-left px-3 py-2 rounded-lg text-[12px] text-[#1B1B2F] hover:bg-[#F0F0F8] flex items-center justify-between gap-2"
                        >
                          <span>→ {item.label}</span>
                          {item.badge && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#EEF0FF] text-[#7B68EE]">
                              {item.badge}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex gap-2 ${
                      m.who === "user" ? "flex-row-reverse" : ""
                    }`}
                  >
                    {m.who === "agent" && (
                      <div
                        className="w-[28px] h-[28px] rounded-full bg-[#E1F5EE] flex items-center justify-center shrink-0"
                        aria-hidden
                      >
                        🌿
                      </div>
                    )}
                    <div
                      className={`max-w-[85%] rounded-xl px-3 py-2 ${
                        m.who === "user"
                          ? "bg-[#7B68EE] text-white"
                          : "bg-[#F8F8FC] ring-1 ring-black/5 text-[#1B1B2F]"
                      }`}
                    >
                      <div className="text-[12px] whitespace-pre-wrap">
                        {m.text}
                      </div>
                      <div
                        className={`text-[10px] mt-1 ${
                          m.who === "user" ? "text-white/80" : "text-[#6B6B8A]"
                        }`}
                      >
                        {m.ts}
                        {m.replies ? ` • ${m.replies} replies` : ""}
                      </div>
                    </div>
                  </div>
                ))}
                {typing && (
                  <div className="flex gap-2">
                    <div
                      className="w-[28px] h-[28px] rounded-full bg-[#E1F5EE] flex items-center justify-center shrink-0"
                      aria-hidden
                    >
                      🌿
                    </div>
                    <div className="rounded-xl px-3 py-2 bg-[#F8F8FC] ring-1 ring-black/5">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-[#7B68EE] animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-2 h-2 rounded-full bg-[#7B68EE] animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-2 h-2 rounded-full bg-[#7B68EE] animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                )}
                {structuredOutput && (
                  <div className="rounded-xl ring-1 ring-emerald-200 bg-emerald-50/60 p-3">
                    <StructuredOutputPanel data={structuredOutput} />
                  </div>
                )}
                {expertInsights && (
                  <div className="mt-2">
                    <ExpertInsights insight={expertInsights} />
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="text-[12px] text-[#6B6B8A] py-4">
            Chưa có nhiệm vụ được giao. Chuyển sang tab Chat để bắt đầu.
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="shrink-0 p-3 border-t border-[#E8E8F0] bg-[#FFFFFF]">
        <div className="flex gap-2 items-end">
          <button
            type="button"
            className="shrink-0 w-[34px] h-[34px] rounded-lg border border-[#E8E8F0] hover:bg-[#F5F5FA] flex items-center justify-center text-[#6B6B8A]"
            aria-label="Attach"
          >
            <Paperclip className="w-[16px] h-[16px]" />
          </button>
          <div className="flex-1 min-w-0">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Hỏi Tự Minh..."
              rows={1}
              className="w-full min-h-[34px] max-h-[80px] rounded-xl px-3 py-2 bg-[#F8F8FC] outline-none ring-1 ring-black/5 text-[12px] resize-none"
            />
            <div className="flex gap-2 mt-1.5">
              <select
                className="h-[26px] rounded-lg bg-[#F8F8FC] text-[11px] px-2 border border-[#E8E8F0]"
                defaultValue="minhbien"
              >
                <option value="minhbien">Tự Minh ▾</option>
              </select>
              <select
                className="h-[26px] rounded-lg bg-[#F8F8FC] text-[11px] px-2 border border-[#E8E8F0]"
                defaultValue="all"
              >
                <option value="all">All Sources ▾</option>
              </select>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleSend()}
            className="shrink-0 h-[34px] px-3 rounded-lg bg-[#7B68EE] text-white text-[12px] font-semibold hover:opacity-95"
          >
            Gửi
          </button>
        </div>
      </div>
    </div>
  );
}
