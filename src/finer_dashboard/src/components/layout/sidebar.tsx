"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  ArrowRightLeft,
  Binary,
  BookMarked,
  Bot,
  CheckCircle2,
  Gauge,
  Layers3,
  Network,
  Radar,
  Settings,
  Database,
} from "lucide-react";
import { cn } from "@/lib/utils";

type WorkflowItem = {
  tier: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  badge: string;
};

const workflowItems: WorkflowItem[] = [
  {
    tier: "L0",
    label: "Intake",
    description: "原始素材入库与路由",
    icon: ArrowRightLeft,
    badge: "L0",
  },
  {
    tier: "L1",
    label: "Enrichment",
    description: "话题拆分与标的归类",
    icon: Network,
    badge: "L1",
  },
  {
    tier: "L2",
    label: "Library",
    description: "标准化知识资产池",
    icon: BookMarked,
    badge: "L2",
  },
  {
    tier: "L3",
    label: "Parsing",
    description: "OCR、视觉转录与上下文",
    icon: Layers3,
    badge: "L3",
  },
  {
    tier: "L5",
    label: "Extraction",
    description: "候选事件与意图链",
    icon: Bot,
    badge: "L5",
  },
  {
    tier: "L6",
    label: "Review",
    description: "字段修正与歧义裁决",
    icon: CheckCircle2,
    badge: "L6",
  },
  {
    tier: "L8",
    label: "Backtest",
    description: "结果验证与收益复盘",
    icon: Gauge,
    badge: "L8",
  },
];

const integrationItems = [
  {
    tier: "Integrations",
    label: "Sync Hub",
    description: "飞书与 NotebookLM 外部源",
    icon: Activity,
    badge: "EXT",
  },
  {
    tier: "DataSource",
    label: "Data Sources",
    description: "微信公众号与 B站数据源",
    icon: Database,
    badge: "SRC",
  }
];

export function Sidebar({
  activeTier,
  onTierChange,
}: {
  activeTier: string;
  onTierChange: (tier: string) => void;
}) {
  const [stats, setStats] = useState({ intake: 0, library: 0, review: 0 });

  useEffect(() => {
    fetch('/api/stats')
      .then(res => res.json())
      .then(data => {
        if (data?.pulse) {
          setStats(data.pulse);
        }
      })
      .catch(console.error);
  }, [activeTier]);

  const activeItem =
    workflowItems.find((item) => item.tier === activeTier) ?? workflowItems[1];

  const pulseItems = [
    { label: "Ingest", value: stats.intake.toString(), tone: "text-[var(--accent-teal)]" },
    { label: "Library", value: stats.library.toString(), tone: "text-[var(--accent-gold)]" },
    { label: "Review", value: stats.review.toString(), tone: "text-morningstar-red" },
  ];

  return (
    <aside className="w-72 editorial-panel h-full flex flex-col z-20 transition-all duration-300">
      <div className="px-8 pt-8 pb-6 border-b border-[rgba(95,67,40,0.12)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-sm bg-morningstar-red flex items-center justify-center shadow-md">
            <Activity className="text-white w-5 h-5" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Finer OS
            </h1>
            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--ink-soft)] mt-1">
              Evidence-first research ops
            </p>
          </div>
        </div>
      </div>

      <div className="px-6 pt-6">
        <div className="rounded-2xl border border-[rgba(95,67,40,0.12)] bg-[rgba(255,252,247,0.74)] px-5 py-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-[var(--ink-soft)] uppercase tracking-[0.18em]">
              Current workflow
            </div>
            <span className="rounded-full bg-[rgba(159,29,34,0.08)] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-morningstar-red">
              {activeItem.badge}
            </span>
          </div>
          <div className="mt-4">
            <div className="text-lg font-bold text-foreground">{activeItem.label}</div>
            <p className="mt-1 text-[12px] leading-relaxed text-[var(--ink-soft)]">
              {activeItem.description}
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto finer-scrollbar px-5 py-6 space-y-8">
        <div className="space-y-2">
          <div className="px-3 text-[10px] font-bold text-[var(--ink-soft)] uppercase tracking-[0.16em]">
            Workflow
          </div>

          <div className="space-y-1.5">
            {workflowItems.map((item) => {
              const isActive = item.tier === activeTier;

              return (
                <button
                  key={item.tier}
                  onClick={() => onTierChange(item.tier)}
                  className={cn(
                    "w-full rounded-2xl border px-4 py-3 text-left transition-all duration-150",
                    isActive
                      ? "border-[rgba(159,29,34,0.2)] bg-[rgba(159,29,34,0.06)] shadow-sm"
                      : "border-transparent bg-transparent hover:border-[rgba(95,67,40,0.1)] hover:bg-[rgba(255,252,247,0.62)]"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 rounded-xl border p-2.5",
                        isActive
                          ? "border-[rgba(159,29,34,0.16)] bg-white text-morningstar-red"
                          : "border-[rgba(95,67,40,0.1)] bg-[rgba(99,76,55,0.04)] text-[var(--ink-soft)]"
                      )}
                    >
                      <item.icon className="w-4 h-4" strokeWidth={1.6} />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <span
                          className={cn(
                            "text-[13px] font-bold",
                            isActive ? "text-morningstar-red" : "text-foreground"
                          )}
                        >
                          {item.label}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--ink-soft)]">
                          {item.badge}
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] leading-relaxed text-[var(--ink-soft)]">
                        {item.description}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <div className="px-3 text-[10px] font-bold text-[var(--ink-soft)] uppercase tracking-[0.16em]">
            Integrations
          </div>

          <div className="space-y-1.5">
            {integrationItems.map((item) => {
              const isActive = item.tier === activeTier;

              return (
                <button
                  key={item.tier}
                  onClick={() => onTierChange(item.tier)}
                  className={cn(
                    "w-full rounded-2xl border px-4 py-3 text-left transition-all duration-150",
                    isActive
                      ? "border-[rgba(159,29,34,0.2)] bg-[rgba(159,29,34,0.06)] shadow-sm"
                      : "border-transparent bg-transparent hover:border-[rgba(95,67,40,0.1)] hover:bg-[rgba(255,252,247,0.62)]"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 rounded-xl border p-2.5",
                        isActive
                          ? "border-[rgba(159,29,34,0.16)] bg-white text-morningstar-red"
                          : "border-[rgba(95,67,40,0.1)] bg-[rgba(99,76,55,0.04)] text-[var(--ink-soft)]"
                      )}
                    >
                      <item.icon className="w-4 h-4" strokeWidth={1.6} />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <span
                          className={cn(
                            "text-[13px] font-bold",
                            isActive ? "text-morningstar-red" : "text-foreground"
                          )}
                        >
                          {item.label}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--ink-soft)]">
                          {item.badge}
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] leading-relaxed text-[var(--ink-soft)]">
                        {item.description}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <div className="px-3 text-[10px] font-bold text-[var(--ink-soft)] uppercase tracking-[0.16em]">
            Pipeline Pulse
          </div>

          <div className="rounded-2xl border border-[rgba(95,67,40,0.12)] bg-[rgba(255,252,247,0.6)] p-4">
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-foreground/70">
              <Radar className="w-4 h-4 text-morningstar-red" strokeWidth={1.6} />
              Active Asset Surface
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2">
              {pulseItems.map((item) => (
                <div
                  key={item.label}
                  className="rounded-xl border border-[rgba(95,67,40,0.1)] bg-white/80 px-3 py-3"
                >
                  <div className={cn("text-lg font-bold tabular-nums", item.tone)}>
                    {item.value}
                  </div>
                  <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-[var(--ink-soft)]">
                    {item.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="px-3 text-[10px] font-bold text-[var(--ink-soft)] uppercase tracking-[0.16em]">
            Provenance
          </div>
          <div className="rounded-2xl border border-[rgba(95,67,40,0.12)] bg-[rgba(255,252,247,0.6)] p-4">
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-foreground/70">
              <Binary className="w-4 h-4 text-[var(--accent-gold)]" strokeWidth={1.6} />
              Pipeline badges remain visible
            </div>
            <p className="mt-3 text-[12px] leading-relaxed text-[var(--ink-soft)]">
              `L0-L8` 现在只作为证据链和运行状态的标识，不再作为主导航心智模型。
            </p>
          </div>
        </div>
      </nav>

      <div className="p-6 mt-auto border-t border-[rgba(95,67,40,0.12)] bg-[rgba(255,252,247,0.5)]">
        <a href="/settings" className="w-full flex items-center gap-3 px-3 py-2 text-foreground/60 hover:text-morningstar-red transition-colors text-xs font-bold">
          <Settings className="w-4 h-4" strokeWidth={1.5} />
          <span>系统设置 / SYSTEM</span>
        </a>
      </div>
    </aside>
  );
}
