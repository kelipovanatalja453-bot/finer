"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Calendar,
  Target,
  BarChart3,
  PieChart,
  Loader2,
  FileText,
  Tag,
} from "lucide-react";
import type { KOL, KOLTimelineEvent, NameLineage } from "@/lib/contracts";

type KOLDetail = KOL & {
  stats: {
    totalOpinions: number;
    correctCount: number;
    avgReturn: number;
    maxReturn: number;
    minReturn: number;
    avgHoldingDays: number;
  };
  timeline: (KOLTimelineEvent & {
    nameLineage?: NameLineage;
    contentVersionId?: string;
  })[];
};

const mockDetail: KOLDetail = {
  id: "kol-1",
  name: "投研老王",
  platform: "wechat",
  platformId: "xxx123",
  overallScore: 4.2,
  dimensionScores: {
    accuracy: 4.5,
    timeliness: 4.0,
    clarity: 3.8,
    depth: 4.2,
    consistency: 4.3,
  },
  accuracy: 68,
  avgReturn: 12.5,
  totalOpinions: 156,
  lastActive: "2026-04-23",
  tags: ["科技", "半导体"],
  enabled: true,
  stats: {
    totalOpinions: 156,
    correctCount: 106,
    avgReturn: 12.5,
    maxReturn: 45.2,
    minReturn: -15.3,
    avgHoldingDays: 23,
  },
  timeline: [
    {
      id: "e1",
      kolId: "kol-1",
      date: "2026-04-20",
      ticker: "NVDA",
      direction: "bullish",
      summary: "半导体周期底部已过，AI需求持续强劲",
      return: 8.5,
      contentVersionId: "cv-001",
      nameLineage: {
        originalFilename: "投研老王_20260420_半导体观点.xlsx",
        f0DisplayName: "投研老王 - 半导体周期分析",
        f1EnvelopeTitle: "半导体行业周期底部判断与AI需求展望",
      },
    },
    {
      id: "e2",
      kolId: "kol-1",
      date: "2026-04-15",
      ticker: "AAPL",
      direction: "neutral",
      summary: "财报前观望，关注服务收入增速",
      contentVersionId: "cv-002",
    },
    {
      id: "e3",
      kolId: "kol-1",
      date: "2026-04-10",
      ticker: "TSLA",
      direction: "bearish",
      summary: "估值过高，竞争加剧",
      return: -5.2,
      // No contentVersionId — tests graceful handling of missing version
      nameLineage: {
        originalFilename: "TSLA_analysis.pdf",
        materializedFilename: "F1_TSLA_analysis_cv-003.json",
      },
    },
  ],
};

function getDirectionColor(direction: string): string {
  switch (direction) {
    case "bullish":
      return "text-green-600 bg-green-50";
    case "bearish":
      return "text-red-600 bg-red-50";
    default:
      return "text-amber-600 bg-amber-50";
  }
}

function getDirectionLabel(direction: string): string {
  switch (direction) {
    case "bullish":
      return "看多";
    case "bearish":
      return "看空";
    default:
      return "中性";
  }
}

/** Display name lineage for an asset, showing all known names across pipeline stages. */
function NameLineageDisplay({ lineage }: { lineage: NameLineage }) {
  const entries = [
    { label: "原始文件名", value: lineage.originalFilename },
    { label: "F0 显示名", value: lineage.f0DisplayName },
    { label: "F1 标题", value: lineage.f1EnvelopeTitle },
    { label: "拆分文件名", value: lineage.splitFilename },
    { label: "物化文件名", value: lineage.materializedFilename },
  ].filter((e) => e.value);

  if (entries.length === 0) return null;

  return (
    <div className="mt-3 p-3 bg-stone-50 rounded-md border border-stone-100">
      <div className="flex items-center gap-2 mb-2 text-xs font-medium text-foreground/60">
        <Tag className="w-3 h-3" />
        <span>名称沿革</span>
      </div>
      <div className="space-y-1.5">
        {entries.map((entry) => (
          <div key={entry.label} className="flex items-baseline gap-2 text-xs">
            <span className="text-foreground/50 w-20 flex-shrink-0">{entry.label}</span>
            <span className="text-foreground/80 font-mono break-all">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function KOLDetailPage() {
  const params = useParams();
  const [kol, setKOL] = useState<KOLDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"timeline" | "radar" | "returns">(
    "timeline"
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      setKOL(mockDetail);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [params.id]);

  if (loading) {
    return (
      <div className="container py-8 h-[80vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-foreground/30" />
      </div>
    );
  }

  if (!kol) {
    return (
      <div className="container py-8">
        <div className="text-center text-foreground/60">KOL 不存在</div>
      </div>
    );
  }

  return (
    <div className="container py-8">
      {/* Back link */}
      <Link
        href="/kol"
        className="inline-flex items-center gap-2 text-sm text-foreground/60 hover:text-foreground mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        返回 KOL 列表
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{kol.name}</h1>
          <p className="text-sm text-foreground/60 mt-1">
            {kol.platform} · {kol.stats.totalOpinions} 条观点
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold">{kol.overallScore.toFixed(1)}</div>
          <div className="text-xs text-foreground/50 uppercase tracking-wider">
            综合评分
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            准确率
          </div>
          <div className="text-2xl font-bold">
            {((kol.stats.correctCount / kol.stats.totalOpinions) * 100).toFixed(1)}%
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            平均收益
          </div>
          <div
            className={cn(
              "text-2xl font-bold flex items-center gap-2",
              kol.stats.avgReturn >= 0 ? "text-green-600" : "text-red-600"
            )}
          >
            {kol.stats.avgReturn >= 0 ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )}
            {kol.stats.avgReturn.toFixed(1)}%
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            最大收益
          </div>
          <div className="text-2xl font-bold text-green-600">
            +{kol.stats.maxReturn.toFixed(1)}%
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            平均持仓
          </div>
          <div className="text-2xl font-bold">{kol.stats.avgHoldingDays} 天</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-stone-200 mb-6">
        {[
          { key: "timeline", label: "时间线", icon: Calendar },
          { key: "radar", label: "能力雷达", icon: PieChart },
          { key: "returns", label: "收益曲线", icon: BarChart3 },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.key
                  ? "border-morningstar-red text-foreground"
                  : "border-transparent text-foreground/60 hover:text-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === "timeline" && (
        <div className="space-y-4">
          {kol.timeline.map((event) => (
            <div
              key={event.id}
              className="bg-white border border-stone-200 rounded-lg p-4 hover:border-stone-300 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-bold">{event.ticker}</span>
                    <span
                      className={cn(
                        "px-2 py-0.5 text-xs font-medium rounded",
                        getDirectionColor(event.direction)
                      )}
                    >
                      {getDirectionLabel(event.direction)}
                    </span>
                    <span className="text-xs text-foreground/50">{event.date}</span>
                    {event.contentVersionId && (
                      <span className="text-[10px] font-mono text-foreground/30 px-1.5 py-0.5 bg-stone-50 rounded">
                        {event.contentVersionId}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-foreground/70">{event.summary}</p>
                  {/* Name lineage detail */}
                  {event.nameLineage && (
                    <NameLineageDisplay lineage={event.nameLineage} />
                  )}
                </div>
                {event.return !== undefined && (
                  <div
                    className={cn(
                      "text-lg font-bold ml-4",
                      event.return >= 0 ? "text-green-600" : "text-red-600"
                    )}
                  >
                    {event.return >= 0 ? "+" : ""}
                    {event.return.toFixed(1)}%
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "radar" && (
        <div className="bg-white border border-stone-200 rounded-lg p-8">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {Object.entries(kol.dimensionScores).map(([key, value]) => {
              const labels: Record<string, string> = {
                accuracy: "准确度",
                timeliness: "时效性",
                clarity: "清晰度",
                depth: "深度",
                consistency: "一致性",
              };
              return (
                <div key={key}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{labels[key]}</span>
                    <span className="text-sm font-bold">{value.toFixed(1)}</span>
                  </div>
                  <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-morningstar-red rounded-full transition-all"
                      style={{ width: `${(value / 5) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === "returns" && (
        <div className="bg-white border border-stone-200 rounded-lg p-8">
          <div className="h-64 flex items-center justify-center text-foreground/40">
            <div className="text-center">
              <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>收益曲线可视化</p>
              <p className="text-xs mt-1">（待实现）</p>
            </div>
          </div>
        </div>
      )}

      {/* Backtest Link */}
      <div className="mt-8 flex justify-end">
        <Link
          href={`/kol/${params.id}/backtest`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-morningstar-red text-white rounded-md hover:bg-morningstar-red/90 transition-colors text-sm font-medium"
        >
          <Target className="w-4 h-4" />
          查看回测详情
        </Link>
      </div>
    </div>
  );
}
