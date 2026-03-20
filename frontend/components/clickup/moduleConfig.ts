/**
 * Module configuration for TuminhAGI Platform — ClickUp-style navigation.
 */

export type ModuleId =
  | "home"
  | "y_hoc"
  | "code"
  | "hoc_tap"
  | "du_lieu"
  | "cong_dong"
  | "nghien_cuu"
  | "minh_bien"
  | "tu_dong"
  | "workspace"
  | "ghi_chu"
  | "muc_tieu"
  | "thoi_gian";

export type ModuleConfig = {
  id: ModuleId;
  label: string;
  shortLabel: string;
  emoji: string;
  color: string;
  bgColor: string;
  pageTitle: string;
  description: string;
  phase?: string;
};

export const MODULE_COLORS: Record<string, { color: string; bg: string }> = {
  y_hoc: { color: "#0F6E56", bg: "#E1F5EE" },
  code: { color: "#7B68EE", bg: "#EEEDFE" },
  hoc_tap: { color: "#185FA5", bg: "#E6F1FB" },
  du_lieu: { color: "#854F0B", bg: "#FAEEDA" },
  cong_dong: { color: "#993C1D", bg: "#FAECE7" },
  nghien_cuu: { color: "#993556", bg: "#FBEAF0" },
  default: { color: "#5F5E5A", bg: "#F1EFE8" },
};

export const MODULES: ModuleConfig[] = [
  {
    id: "home",
    label: "Home",
    shortLabel: "Home",
    emoji: "🏠",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "Home — Tự Minh Platform",
    description: "Trang chủ",
  },
  {
    id: "y_hoc",
    label: "🌿 Y học",
    shortLabel: "Y học",
    emoji: "🌿",
    color: MODULE_COLORS.y_hoc.color,
    bgColor: MODULE_COLORS.y_hoc.bg,
    pageTitle: "🌿 Tự Minh — Tự Minh V9.4",
    description: "Hệ thống chẩn đoán y khoa, phác đồ điều trị, thuốc Nam.",
  },
  {
    id: "code",
    label: "💻 Code",
    shortLabel: "Code",
    emoji: "💻",
    color: MODULE_COLORS.code.color,
    bgColor: MODULE_COLORS.code.bg,
    pageTitle: "💻 Code Editor — Coming soon",
    description: "Trình soạn thảo code tích hợp AI.",
    phase: "Phase 2",
  },
  {
    id: "hoc_tap",
    label: "📚 Học tập",
    shortLabel: "Học tập",
    emoji: "📚",
    color: MODULE_COLORS.hoc_tap.color,
    bgColor: MODULE_COLORS.hoc_tap.bg,
    pageTitle: "📚 Không gian học tập — Coming soon",
    description: "Quản lý tài liệu, flashcard, ôn tập.",
    phase: "Phase 2",
  },
  {
    id: "du_lieu",
    label: "📊 Dữ liệu",
    shortLabel: "Dữ liệu",
    emoji: "📊",
    color: MODULE_COLORS.du_lieu.color,
    bgColor: MODULE_COLORS.du_lieu.bg,
    pageTitle: "📊 Dữ liệu — Coming soon",
    description: "Phân tích dữ liệu, biểu đồ, báo cáo.",
    phase: "Phase 3",
  },
  {
    id: "cong_dong",
    label: "🤝 Cộng đồng",
    shortLabel: "Cộng đồng",
    emoji: "🤝",
    color: MODULE_COLORS.cong_dong.color,
    bgColor: MODULE_COLORS.cong_dong.bg,
    pageTitle: "🤝 Cộng đồng — Coming soon",
    description: "Thảo luận, chia sẻ kinh nghiệm.",
    phase: "Phase 3",
  },
  {
    id: "nghien_cuu",
    label: "🧬 Nghiên cứu",
    shortLabel: "Nghiên cứu",
    emoji: "🧬",
    color: MODULE_COLORS.nghien_cuu.color,
    bgColor: MODULE_COLORS.nghien_cuu.bg,
    pageTitle: "🧬 Nghiên cứu — Coming soon",
    description: "Quản lý nghiên cứu, thí nghiệm.",
    phase: "Phase 4",
  },
  {
    id: "minh_bien",
    label: "🤖 Tự Minh",
    shortLabel: "Tự Minh",
    emoji: "🤖",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "🤖 Tự Minh AI — Coming soon",
    description: "Trợ lý AI đa nhiệm.",
    phase: "Phase 4",
  },
  {
    id: "tu_dong",
    label: "⚡ Tự động",
    shortLabel: "Tự động",
    emoji: "⚡",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "⚡ Tự động hóa — Coming soon",
    description: "Workflow, automation.",
    phase: "Phase 4",
  },
  {
    id: "workspace",
    label: "🗂️ Workspace",
    shortLabel: "Workspace",
    emoji: "🗂️",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "🗂️ Workspace — Coming soon",
    description: "Quản lý không gian làm việc.",
    phase: "Phase 5",
  },
  {
    id: "ghi_chu",
    label: "📝 Ghi chú",
    shortLabel: "Ghi chú",
    emoji: "📝",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "📝 Ghi chú — Coming soon",
    description: "Ghi chú nhanh, gắn thẻ.",
    phase: "Phase 5",
  },
  {
    id: "muc_tieu",
    label: "🎯 Mục tiêu",
    shortLabel: "Mục tiêu",
    emoji: "🎯",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "🎯 Mục tiêu — Coming soon",
    description: "OKR, theo dõi tiến độ.",
    phase: "Phase 5",
  },
  {
    id: "thoi_gian",
    label: "⏱️ Thời gian",
    shortLabel: "Thời gian",
    emoji: "⏱️",
    color: MODULE_COLORS.default.color,
    bgColor: MODULE_COLORS.default.bg,
    pageTitle: "⏱️ Quản lý thời gian — Coming soon",
    description: "Time tracking, Pomodoro.",
    phase: "Phase 5",
  },
];

export const getModuleById = (id: ModuleId): ModuleConfig | undefined =>
  MODULES.find((m) => m.id === id);

export const NAV_STRIP_MODULES: ModuleId[] = [
  "home",
  "y_hoc",
  "code",
  "hoc_tap",
  "du_lieu",
  "cong_dong",
];

export const MORE_GRID_MODULES: ModuleId[] = [
  "y_hoc",
  "code",
  "hoc_tap",
  "du_lieu",
  "cong_dong",
  "nghien_cuu",
  "minh_bien",
  "tu_dong",
  "workspace",
  "ghi_chu",
  "muc_tieu",
  "thoi_gian",
];
