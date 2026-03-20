"use client";

import React, { useState, useCallback, useEffect } from "react";
import ClickUpShell from "@/components/clickup/ClickUpShell";
import HomeView from "@/components/clickup/HomeView";
import MainContentList from "@/components/clickup/MainContentList";
import MinhBienAgentPanel from "@/components/clickup/MinhBienAgentPanel";
import ComingSoonPlaceholder from "@/components/clickup/ComingSoonPlaceholder";
import { getModuleById, type ModuleId } from "@/components/clickup/moduleConfig";
import { detectEmergencyFromUserText } from "@/lib/emergency";
import {
  parseSymptomsAndContext,
  postDiagnoseV2,
  formatDiagnosisForDisplay,
} from "@/lib/diagnose-client";

export default function Page() {
  const [activeModule, setActiveModule] = useState<ModuleId>("home");
  const [isEmergency, setIsEmergency] = useState(false);
  const [emergencyReason, setEmergencyReason] = useState("");
  const [diagnosisSummary, setDiagnosisSummary] = useState<string | null>(null);

  const mod = getModuleById(activeModule);
  const pageTitle = mod?.pageTitle ?? "Tự Minh Platform";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const q = new URLSearchParams(window.location.search).get("emergency");
    if (q === "1" || q === "true") {
      setIsEmergency(true);
      setEmergencyReason("Chế độ kiểm tra: ?emergency=1 — gọi cấp cứu nếu cần.");
      setDiagnosisSummary(null);
    }
  }, []);

  const handleSelectModule = useCallback((id: ModuleId) => {
    setActiveModule(id);
  }, []);

  const onDiagnose = useCallback(async (text: string) => {
    const local = detectEmergencyFromUserText(text);
    const { symptoms, context } = parseSymptomsAndContext(text);

    let data = null as Awaited<ReturnType<typeof postDiagnoseV2>> | null;
    try {
      data = await postDiagnoseV2(symptoms, context);
    } catch {
      data = { error: "Network error" };
    }

    const apiErr = Boolean(data?.error) && !data?.candidates?.length;
    const apiEm = Boolean(data?.is_emergency);

    const emergency = local.emergency || apiEm;
    const reason =
      (data?.emergency_reason && String(data.emergency_reason)) ||
      local.reason ||
      (apiEm ? "Pipeline đánh dấu cấp cứu." : "");

    const { summaryLines, agentReply } = formatDiagnosisForDisplay(data || {}, emergency);
    const summaryText = summaryLines.join("\n");

    if (emergency) {
      setIsEmergency(true);
      setEmergencyReason(reason || "Tình huống khẩn cấp.");
      setDiagnosisSummary(
        apiErr
          ? `${summaryText}\n\n(Không kết nối được máy chủ chẩn đoán đầy đủ — vẫn ưu tiên cấp cứu.)`
          : summaryText || reason
      );
      return { isEmergency: true, agentReply: "" };
    }

    setDiagnosisSummary(null);
    if (apiErr) {
      return {
        isEmergency: false,
        agentReply:
          "Không gọi được /diagnose/v2 (kiểm tra API Python port 8000 và `npm run dev`).\n" +
          "Gợi ý: chạy uvicorn api_server:app --port 8000",
      };
    }
    return {
      isEmergency: false,
      agentReply: agentReply || summaryText || "Không có kết quả chi tiết.",
    };
  }, []);

  const mainContent =
    activeModule === "home" ? (
      <HomeView onSelectModule={handleSelectModule} />
    ) : activeModule === "y_hoc" ? (
      <MainContentList onSessionSelect={(id) => console.log("session", id)} />
    ) : mod ? (
      <ComingSoonPlaceholder module={mod} />
    ) : (
      <div className="h-full flex items-center justify-center text-[#6B6B8A]">
        Chọn module để bắt đầu
      </div>
    );

  const agentPanel = (
    <MinhBienAgentPanel
      activeModule={activeModule}
      isEmergency={isEmergency}
      emergencyReason={emergencyReason}
      diagnosisSummary={diagnosisSummary}
      structuredOutput={null}
      expertInsights={null}
      onDiagnose={onDiagnose}
      onSuggestionClick={(label) => console.log("suggestion", label)}
    />
  );

  return (
    <ClickUpShell
      onOpenCommandPalette={() => {}}
      activeModule={activeModule}
      onSelectModule={handleSelectModule}
      pageTitle={pageTitle}
      main={mainContent}
      agentPanel={agentPanel}
      isEmergency={isEmergency}
    />
  );
}
