"use client";

import React, { useCallback, useState } from "react";

export interface ContributeCase {
  id: string;
  label: string;
  symptoms: string[];
  diagnosis?: string;
  treatment?: string;
  outcome?: string;
  durationDays?: number;
  herbsUsed?: string[];
  ageGroup?: string;
  region?: string;
  season?: string;
}

export interface ContributePanelProps {
  cases?: ContributeCase[];
  onContribute?: (payload: ContributePayload) => Promise<{ accepted: boolean; reason?: string }>;
  onClose?: () => void;
  className?: string;
}

export interface ContributePayload {
  type: string;
  content: {
    symptoms: string[];
    diagnosis: string;
    treatment: string;
    outcome: string;
    duration: number;
    herbs_used: string[];
  };
  metadata: {
    region: string;
    age_group: string;
    season: string;
  };
  privacy: {
    is_anonymous: true;
    no_personal_info: true;
    consent_given: boolean;
  };
  validation: {
    evidence_level: string;
    source: string;
    verified_by_md: boolean;
  };
}

const DEFAULT_CASES: ContributeCase[] = [
  {
    id: "001",
    label: "Đau dạ dày",
    symptoms: ["đau thượng vị", "buồn nôn", "đầy hơi"],
    diagnosis: "K29.7",
    treatment: "Sắc uống Gừng, Nghệ",
    outcome: "improved",
    durationDays: 7,
    herbsUsed: ["Gừng", "Nghệ vàng"],
    ageGroup: "người lớn",
    region: "miền Nam",
    season: "mùa hè",
  },
  {
    id: "003",
    label: "Ho mạn tính",
    symptoms: ["ho kéo dài", "đờm trắng"],
    diagnosis: "R05",
    treatment: "Húng chanh, Kinh giới",
    outcome: "improved",
    durationDays: 14,
    herbsUsed: ["Húng chanh", "Kinh giới"],
    ageGroup: "người lớn",
    region: "Hà Nội",
    season: "mùa đông",
  },
];

function buildPayload(
  case_: ContributeCase,
  consent: boolean
): ContributePayload {
  return {
    type: "treatment_outcome",
    content: {
      symptoms: case_.symptoms || [],
      diagnosis: case_.diagnosis || "",
      treatment: case_.treatment || "",
      outcome: case_.outcome || "unknown",
      duration: case_.durationDays || 0,
      herbs_used: case_.herbsUsed || [],
    },
    metadata: {
      region: case_.region || "không xác định",
      age_group: case_.ageGroup || "adult",
      season: case_.season || "không xác định",
    },
    privacy: {
      is_anonymous: true,
      no_personal_info: true,
      consent_given: consent,
    },
    validation: {
      evidence_level: "self_reported",
      source: "tự báo cáo",
      verified_by_md: false,
    },
  };
}

export default function ContributePanel({
  cases = DEFAULT_CASES,
  onContribute,
  onClose,
  className = "",
}: ContributePanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!consent) {
      setMessage({ type: "error", text: "Vui lòng đồng ý chia sẻ ẩn danh." });
      return;
    }
    const firstId = Array.from(selected)[0];
    if (!firstId) {
      setMessage({ type: "error", text: "Vui lòng chọn ít nhất một ca khám." });
      return;
    }
    const case_ = cases.find((c) => c.id === firstId);
    if (!case_) return;

    setSubmitting(true);
    setMessage(null);
    try {
      const payload = buildPayload(case_, consent);
      const handler = onContribute ?? defaultContribute;
      const res = await handler(payload);
      if (res.accepted) {
        setMessage({ type: "success", text: "Đã đóng góp thành công. Cảm ơn bạn!" });
        setSelected(new Set());
        setConsent(false);
      } else {
        setMessage({ type: "error", text: res.reason || "Đóng góp thất bại." });
      }
    } catch (e) {
      setMessage({ type: "error", text: String(e) });
    } finally {
      setSubmitting(false);
    }
  }, [consent, selected, cases, onContribute]);

async function defaultContribute(payload: ContributePayload): Promise<{
  accepted: boolean;
  reason?: string;
}> {
  const res = await fetch("/api/knowledge/contribute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await res.json().catch(() => ({}))) as {
    accepted?: boolean;
    reason?: string;
  };
  return {
    accepted: Boolean(data.accepted),
    reason: data.reason,
  };
}

  const previewCase = Array.from(selected)[0]
    ? cases.find((c) => c.id === Array.from(selected)[0])
    : null;

  return (
    <div
      className={
        "rounded-xl border border-green-200 bg-white shadow-md overflow-hidden " + className
      }
    >
      <div className="p-4 sm:p-5 bg-gradient-to-r from-green-50 to-emerald-50 border-b border-green-100">
        <h2 className="text-lg font-semibold text-green-900 flex items-center gap-2">
          <span>🌿</span> Đóng góp cho cộng đồng
        </h2>
        <p className="text-sm text-green-800 mt-1">
          Chia sẻ kinh nghiệm của bạn giúp cải thiện Tự Minh cho 4.5 tỷ người.
        </p>
      </div>

      <div className="p-4 sm:p-5 space-y-4">
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">
            Chọn ca khám muốn chia sẻ:
          </p>
          <ul className="space-y-2">
            {cases.map((c) => (
              <li key={c.id} className="flex items-start gap-3">
                <input
                  type="checkbox"
                  id={`case-${c.id}`}
                  checked={selected.has(c.id)}
                  onChange={() => toggle(c.id)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                />
                <label htmlFor={`case-${c.id}`} className="text-sm text-gray-800 cursor-pointer">
                  <span className="font-medium">Ca khám #{c.id}</span> — {c.label}
                  <span className="block text-xs text-gray-500 mt-0.5">
                    (đã ẩn thông tin cá nhân)
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>

        {previewCase && (
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Preview data sẽ chia sẻ:</p>
            <div className="rounded-lg border border-green-200 bg-green-50/50 p-3 text-sm text-gray-800 space-y-1">
              <p>
                <strong>Triệu chứng:</strong> {previewCase.symptoms?.join(", ") || "—"}
              </p>
              <p>
                <strong>Nhóm tuổi:</strong> {previewCase.ageGroup || "—"}
              </p>
              <p>
                <strong>Khu vực:</strong> {previewCase.region || "—"}
              </p>
              <p>
                <strong>Kết quả:</strong>{" "}
                {previewCase.outcome === "improved"
                  ? "cải thiện"
                  : previewCase.outcome === "recovered"
                    ? "khỏi"
                    : previewCase.outcome || "—"}
                {previewCase.durationDays
                  ? ` sau ${previewCase.durationDays} ngày`
                  : ""}
              </p>
              <p>
                <strong>Thuốc Nam:</strong> {previewCase.herbsUsed?.join(", ") || "—"}
              </p>
              <p className="pt-2 text-green-700 font-medium">✓ Không có thông tin cá nhân</p>
            </div>
          </div>
        )}

        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="consent"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          <label htmlFor="consent" className="text-sm text-gray-700 cursor-pointer">
            <strong>Tôi đồng ý chia sẻ ẩn danh</strong>
            <br />
            <span className="text-gray-600">
              Tôi hiểu data này sẽ giúp cải thiện Tự Minh cho mọi người
            </span>
          </label>
        </div>

        {message && (
          <div
            className={
              "rounded-lg p-3 text-sm " +
              (message.type === "success"
                ? "bg-green-100 text-green-800"
                : "bg-red-50 text-red-800")
            }
          >
            {message.text}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-sm font-medium"
            >
              Hủy
            </button>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
          >
            {submitting ? "Đang gửi…" : "Đóng góp →"}
          </button>
        </div>
      </div>

      <div className="px-4 sm:px-5 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-600">
        <p className="font-medium text-gray-700">🔒 Data của bạn luôn thuộc về bạn</p>
        <p>Chúng tôi không bao giờ tự động thu thập hay bán dữ liệu.</p>
      </div>
    </div>
  );
}
