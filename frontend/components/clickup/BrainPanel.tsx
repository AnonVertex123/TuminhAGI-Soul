"use client";

import React, { useMemo, useState } from "react";
import { Paperclip } from "lucide-react";
import ExpertInsights, { type ExpertInsightPayload } from "../ExpertInsights";
import { type StructuredOutputData } from "../StructuredOutputPanel";
import DonutChart from "./DonutChart";

type Candidate = {
  icd_reference: string;
  name: string;
  critic_status: string;
  confidence: number | null;
  description_phrase: string;
};

export default function BrainPanel({
  structuredOutput,
  expertInsights,
  isEmergency,
}: {
  structuredOutput: StructuredOutputData | null;
  expertInsights: ExpertInsightPayload | null;
  isEmergency: boolean;
}) {
  const [brainInput, setBrainInput] = useState("");

  const topCandidates = useMemo(() => {
    const arr = structuredOutput?.possible_conditions ?? [];
    return arr.slice(0, 3) as Candidate[];
  }, [structuredOutput]);

  const urgencyLabel = structuredOutput?.urgency ?? "Theo dõi tại nhà";

  const recommendedTrack = useMemo(() => {
    if (!structuredOutput) return "herbal_only";
    if (urgencyLabel === "CẤP CỨU NGAY") return "emergency";
    if (urgencyLabel === "Cần khám trong ngày") return "both";
    return "herbal_only";
  }, [structuredOutput, urgencyLabel]);

  const emergencyContent = (
    <div className="h-full flex items-center justify-center p-3">
      <div className="w-full rounded-2xl border-2 border-red-500 bg-red-50 animate-pulse p-4 flex flex-col items-center text-center gap-2">
        <div className="text-2xl" aria-hidden>
          ⚠️
        </div>
        <div className="text-[14px] font-extrabold text-[#7A0C0C]">KHẨN CẤP</div>
        <div className="text-[12px] font-semibold text-[#7A0C0C]">Gọi 115 ngay lập tức</div>
        <div className="text-[11px] text-[#8B5A5A]">
          Không tự điều trị bằng thuốc Nam. Vui lòng đến cơ sở y tế gần nhất ngay.
        </div>
      </div>
    </div>
  );

  return (
    <div className="w-[280px] shrink-0 border-l border-[#E8E8F0] bg-[#F8F8FC] h-full overflow-hidden flex flex-col">
      <div className="flex-1 overflow-y-auto p-3">
        {isEmergency ? (
          emergencyContent
        ) : (
          <div className="space-y-3">
            {/* Header */}
            <div className="rounded-2xl bg-[#FFFFFF] ring-1 ring-black/5 p-3">
              <div className="text-[13px] font-extrabold text-[#1B1B2F] flex items-center gap-2">
                <span aria-hidden>🌿</span> Tự Minh
              </div>
              <div className="text-[12px] text-[#6B6B8A] mt-1">Xin chào! Tôi có thể giúp gì cho bạn?</div>
            </div>

            {/* Suggested */}
            <div className="rounded-2xl bg-[#FFFFFF] ring-1 ring-black/5 p-3">
              <div className="text-[12px] font-semibold text-[#1B1B2F] mb-2">Gợi ý</div>
              <div className="space-y-2">
                <div className="text-[12px] text-[#6B6B8A]">• Giải thích triệu chứng vừa nhập</div>
                <div className="text-[12px] text-[#6B6B8A]">• Xem lịch sử bệnh nhân</div>
                <div className="text-[12px] text-[#6B6B8A]">• Tóm tắt phác đồ điều trị</div>
              </div>
            </div>

            {/* Featured actions */}
            <div className="rounded-2xl bg-[#FFFFFF] ring-1 ring-black/5 p-3">
              <div className="text-[12px] font-semibold text-[#1B1B2F] mb-2">Nổi bật</div>
              <div className="space-y-2">
                {[
                  { label: "Chẩn đoán nhanh", badge: "Mới" },
                  { label: "Tạo báo cáo", badge: "Mới" },
                  { label: "Hỏi về thuốc Nam", badge: "Mới" },
                ].map((x) => (
                  <button
                    key={x.label}
                    type="button"
                    className="w-full h-[32px] rounded-xl bg-[#F8F8FC] hover:bg-[#F0F0F8] ring-1 ring-black/5 flex items-center justify-between px-2"
                  >
                    <span className="text-[12px] font-semibold text-[#1B1B2F] truncate">{x.label}</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#EEF0FF] text-[#7B68EE]">
                      {x.badge}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Constitution badge + candidates */}
            <div className="rounded-2xl bg-[#FFFFFF] ring-1 ring-black/5 p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[12px] font-semibold text-[#1B1B2F]">Kết quả</div>
                <div className="text-[11px] text-[#6B6B8A]">Urgency: {urgencyLabel}</div>
              </div>

              <div className="flex items-center justify-between gap-2 mb-3">
                <span className="text-[11px] px-2 py-1 rounded-full bg-[#EEF0FF] text-[#7B68EE] font-semibold">
                  Constitution: Chưa xác định
                </span>
                <span className="text-[11px] px-2 py-1 rounded-full bg-[#F0F0F8] text-[#1B1B2F] font-semibold">
                  Track: {recommendedTrack}
                </span>
              </div>

              <div className="space-y-2">
                {topCandidates.length === 0 ? (
                  <div className="text-[11px] text-[#6B6B8A] leading-relaxed">
                    Chưa có dữ liệu ứng viên. Vui lòng nhập triệu chứng để hệ thống phân tích.
                  </div>
                ) : (
                  topCandidates.map((c) => (
                    <div key={c.icd_reference} className="rounded-xl ring-1 ring-black/5 bg-[#F8F8FC] p-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-[11px] font-mono text-[#1B1B2F] truncate">{c.icd_reference}</div>
                          <div className="text-[11px] text-[#6B6B8A] truncate">{c.description_phrase}</div>
                        </div>
                        <div className="text-[10px] font-bold text-[#7B68EE] shrink-0">
                          {(c.confidence ?? 0).toFixed(0)}%
                        </div>
                      </div>
                      <div className="mt-1 text-[10px] text-[#6B6B8A]">
                        {c.critic_status === "SUGGESTION" ? "Cần xem xét thêm" : c.critic_status === "APPROVED" ? "Đáng tin cậy" : c.critic_status}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Treatment recommendation placeholder */}
              <div className="mt-3">
                <div className="text-[12px] font-semibold text-[#1B1B2F] mb-2">Phác đồ điều trị</div>
                <div className="rounded-xl bg-[#F8F8FC] ring-1 ring-black/5 p-2 text-[11px] text-[#6B6B8A] leading-relaxed">
                  {structuredOutput
                    ? "Hệ thống đang tạo gợi ý phác đồ dựa trên mức độ nguy hiểm và thể trạng. (Nếu bạn bật backend điều trị đầy đủ, thẻ Thuốc Nam sẽ hiển thị tại đây.)"
                    : "Chưa có dữ liệu phác đồ điều trị. Vui lòng chạy chẩn đoán."}
                </div>
              </div>

              {/* Donut chart mini */}
              <div className="mt-3">
                <DonutChart routineValue={7} urgentValue={2} emergencyValue={1} />
              </div>

              {/* Red flags / expert insights */}
              <div className="mt-3">
                <ExpertInsights insight={expertInsights} />
              </div>
            </div>

            {/* Disclaimer */}
            <div className="text-[10px] text-[#6B6B8A] leading-relaxed mt-1">
              * Thông tin chỉ mang tính tham khảo, không thay thế chẩn đoán của bác sĩ.
            </div>
          </div>
        )}
      </div>

      {/* Bottom input (ClickUp-style) */}
      {!isEmergency ? (
        <div className="p-3 border-t border-[#E8E8F0] bg-[#FFFFFF]">
          <div className="flex items-center gap-2">
            <span className="text-[#6B6B8A]" aria-hidden>
              <Paperclip className="w-[16px] h-[16px]" />
            </span>
            <input
              value={brainInput}
              onChange={(e) => setBrainInput(e.target.value)}
              placeholder="Hỏi, tạo, tìm kiếm hoặc @ để đề cập"
              className="flex-1 h-[34px] rounded-xl px-3 bg-[#F8F8FC] outline-none ring-1 ring-black/5 text-[12px]"
            />
            <select
              className="h-[34px] rounded-xl bg-[#F8F8FC] outline-none ring-1 ring-black/5 text-[12px] px-2"
              defaultValue="all"
            >
              <option value="all">All Sources ▾</option>
            </select>
          </div>
        </div>
      ) : (
        <div className="p-3 border-t border-[#E8E8F0] bg-[#FFFFFF]">
          <div className="text-[10px] text-[#6B6B8A]">
            * Thông tin chỉ mang tính tham khảo. Nếu có dấu hiệu nguy hiểm, hãy gọi 115 ngay lập tức.
          </div>
        </div>
      )}
    </div>
  );
}

