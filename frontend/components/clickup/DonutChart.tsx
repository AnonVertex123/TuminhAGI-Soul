"use client";

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

type Slice = { label: string; value: number; color: string };

export default function DonutChart({
  routineValue,
  urgentValue,
  emergencyValue,
}: {
  routineValue: number;
  urgentValue: number;
  emergencyValue: number;
}) {
  const slices: Slice[] = [
    { label: "routine", value: routineValue, color: "#10B981" },
    { label: "urgent", value: urgentValue, color: "#F59E0B" },
    { label: "emergency", value: emergencyValue, color: "#EF4444" },
  ];

  const total = slices.reduce((acc, s) => acc + s.value, 0) || 1;

  return (
    <div className="rounded-xl bg-[#FFFFFF] ring-1 ring-black/5 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[12px] font-semibold text-[#1B1B2F]">
          Phân bố ca theo nhóm bệnh
        </div>
        <div className="text-[11px] text-[#6B6B8A]">{total} tổng</div>
      </div>
      <div className="h-[140px] w-full">
        <ResponsiveContainer width="100%" height={140}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius={45}
              outerRadius={65}
              stroke="none"
            >
              {slices.map((s) => (
                <Cell key={s.label} fill={s.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: any, name: any) => {
                const num = typeof v === "number" ? v : Number(v);
                const pct = Math.round((num / total) * 100);
                return [`${pct}%`, name];
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-[#6B6B8A]">
        <div className="flex items-center gap-2">
          <span className="w-[8px] h-[8px] rounded-full" style={{ background: "#10B981" }} />
          Routine
        </div>
        <div className="flex items-center gap-2">
          <span className="w-[8px] h-[8px] rounded-full" style={{ background: "#F59E0B" }} />
          Urgent
        </div>
        <div className="flex items-center gap-2">
          <span className="w-[8px] h-[8px] rounded-full" style={{ background: "#EF4444" }} />
          Emergency
        </div>
      </div>
    </div>
  );
}

