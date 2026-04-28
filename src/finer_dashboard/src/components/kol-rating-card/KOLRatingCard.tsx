"use client";

import React from "react";
import { StarRating } from "./StarRating";
import { DimensionScores } from "./DimensionScores";
import { PerformanceTimeline } from "./PerformanceTimeline";
import { FocusAreas } from "./FocusAreas";
import { RecentOpinions } from "./RecentOpinions";
import { TrendingUp, TrendingDown, Minus, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

// Types
export interface KOLRating {
  kolId: string;
  name: string;
  avatar?: string;
  platform: string;
  overallRating: number; // 1-5
  totalOpinions: number;
  verifiedOpinions: number;
  accuracyRate: number; // 0-100
  avgReturn: number; // percentage
  rank?: number; // ranking among all KOLs
  badges: string[];
}

export interface DimensionScore {
  name: string;
  score: number; // 0-100
  weight: number; // 0-1
  description?: string;
}

export interface TimelineEvent {
  id: string;
  date: string;
  ticker: string;
  direction: "bullish" | "bearish" | "neutral";
  verified: boolean;
  result?: "profit" | "loss" | "neutral";
  returnRate?: number;
  summary: string;
}

export interface FocusArea {
  name: string;
  count: number;
  accuracy: number; // 0-100
  avgReturn: number;
}

export interface RecentOpinion {
  id: string;
  date: string;
  ticker: string;
  direction: "bullish" | "bearish" | "neutral";
  title: string;
  verified: boolean;
  status: "pending" | "correct" | "incorrect";
  returnRate?: number;
  detailPath?: string;
}

export interface KOLRatingCardProps {
  kolId: string;
  className?: string;
  compact?: boolean;
  showTimeline?: boolean;
  showOpinions?: boolean;
}

// API response type
interface KOLRatingResponse {
  rating: KOLRating;
  dimensions: DimensionScore[];
  timeline: TimelineEvent[];
  focusAreas: FocusArea[];
  recentOpinions: RecentOpinion[];
}

// Mock data for development
const mockKOLRating: KOLRatingResponse = {
  rating: {
    kolId: "kol_001",
    name: "李大霄",
    platform: "微博",
    overallRating: 4,
    totalOpinions: 156,
    verifiedOpinions: 142,
    accuracyRate: 68.3,
    avgReturn: 12.5,
    rank: 23,
    badges: ["金牌分析师", "连续3年准确率>60%"],
  },
  dimensions: [
    { name: "观点准确率", score: 68.3, weight: 0.35, description: "历史观点验证成功率" },
    { name: "止损质量", score: 72.1, weight: 0.20, description: "风险提示及时性与有效性" },
    { name: "一致性", score: 85.6, weight: 0.15, description: "观点逻辑前后一致性" },
    { name: "时效性", score: 91.2, weight: 0.15, description: "观点发布的时效价值" },
    { name: "信息密度", score: 78.4, weight: 0.15, description: "单条观点的有效信息量" },
  ],
  timeline: [
    { id: "t1", date: "2024-04-20", ticker: "NVDA", direction: "bullish", verified: true, result: "profit", returnRate: 15.2, summary: "AI算力龙头，目标价上调" },
    { id: "t2", date: "2024-04-18", ticker: "TSLA", direction: "bearish", verified: true, result: "profit", returnRate: 8.7, summary: "交付量不及预期，建议减仓" },
    { id: "t3", date: "2024-04-15", ticker: "AAPL", direction: "neutral", verified: true, result: "neutral", returnRate: 0.5, summary: "财报前观望" },
    { id: "t4", date: "2024-04-12", ticker: "AMD", direction: "bullish", verified: true, result: "loss", returnRate: -3.2, summary: "MI300放量预期" },
    { id: "t5", date: "2024-04-10", ticker: "META", direction: "bullish", verified: false, summary: "AI广告变现加速" },
  ],
  focusAreas: [
    { name: "AI芯片", count: 45, accuracy: 75.6, avgReturn: 18.3 },
    { name: "新能源", count: 38, accuracy: 62.1, avgReturn: 9.8 },
    { name: "消费电子", count: 28, accuracy: 71.4, avgReturn: 11.2 },
    { name: "云计算", count: 25, accuracy: 68.0, avgReturn: 14.5 },
    { name: "医疗健康", count: 20, accuracy: 55.0, avgReturn: 5.6 },
  ],
  recentOpinions: [
    { id: "o1", date: "2024-04-22", ticker: "MSFT", direction: "bullish", title: "Azure增速超预期，AI云服务领跑", verified: false, status: "pending" },
    { id: "o2", date: "2024-04-21", ticker: "GOOGL", direction: "bullish", title: "Gemini 2.0发布在即，广告业务稳健", verified: true, status: "correct", returnRate: 6.2 },
    { id: "o3", date: "2024-04-19", ticker: "AMZN", direction: "neutral", title: "AWS增速放缓，零售业务承压", verified: true, status: "correct", returnRate: 1.1 },
    { id: "o4", date: "2024-04-17", ticker: "NFLX", direction: "bearish", title: "会员增长见顶，内容成本攀升", verified: true, status: "incorrect", returnRate: -4.3 },
  ],
};

export function KOLRatingCard({
  kolId,
  className,
  compact = false,
  showTimeline = true,
  showOpinions = true,
}: KOLRatingCardProps) {
  const [data, setData] = React.useState<KOLRatingResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/kol/rating/${kolId}`);
        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [kolId]);

  if (loading) {
    return (
      <div className={cn(
        "rounded-2xl border border-[rgba(95,67,40,0.12)] bg-white/80 p-8 shadow-sm",
        className
      )}>
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-morningstar-red" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={cn(
        "rounded-2xl border border-[rgba(95,67,40,0.12)] bg-white/80 p-8 shadow-sm",
        className
      )}>
        <div className="flex items-center justify-center h-48 text-foreground/50">
          <AlertCircle className="w-5 h-5 mr-2" />
          <span className="text-sm">加载失败</span>
        </div>
      </div>
    );
  }

  const { rating, dimensions, timeline, focusAreas, recentOpinions } = data;
  const directionIcon = rating.avgReturn >= 0
    ? <TrendingUp className="w-4 h-4" />
    : <TrendingDown className="w-4 h-4" />;

  return (
    <div className={cn(
      "rounded-2xl border border-[rgba(95,67,40,0.12)] bg-[rgba(255,252,247,0.86)] shadow-lg backdrop-blur-xl overflow-hidden",
      className
    )}>
      {/* Header: Core Rating + Key Metrics */}
      <div className="p-6 border-b border-[rgba(95,67,40,0.12)] bg-gradient-to-b from-white/60 to-transparent">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[rgba(159,29,34,0.1)] to-[rgba(31,106,103,0.1)] flex items-center justify-center text-lg font-bold text-foreground/80 border border-[rgba(95,67,40,0.12)]">
              {rating.name.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-foreground">{rating.name}</h3>
                <span className="text-[10px] font-bold uppercase tracking-widest text-foreground/50 bg-stone-100 px-2 py-0.5 rounded">
                  {rating.platform}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <StarRating rating={rating.overallRating} size="lg" showLabel />
                {rating.rank && (
                  <span className="text-xs text-foreground/60">
                    排名 #{rating.rank}
                  </span>
                )}
              </div>
              {rating.badges.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {rating.badges.map((badge, i) => (
                    <span
                      key={i}
                      className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-[rgba(159,29,34,0.07)] text-morningstar-red border border-[rgba(159,29,34,0.12)]"
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Key Metrics */}
          <div className="flex items-center gap-6">
            <MetricBlock
              label="观点数"
              value={rating.totalOpinions.toString()}
              subLabel={`${rating.verifiedOpinions} 已验证`}
            />
            <MetricBlock
              label="准确率"
              value={`${rating.accuracyRate.toFixed(1)}%`}
              trend={rating.accuracyRate >= 60 ? "up" : rating.accuracyRate >= 40 ? "neutral" : "down"}
            />
            <MetricBlock
              label="平均收益"
              value={`${rating.avgReturn >= 0 ? "+" : ""}${rating.avgReturn.toFixed(1)}%`}
              trend={rating.avgReturn >= 0 ? "up" : "down"}
              icon={directionIcon}
            />
          </div>
        </div>
      </div>

      {/* Body: Dimension Scores */}
      <div className="p-6 border-b border-[rgba(95,67,40,0.08)]">
        <div className="text-[10px] font-bold uppercase tracking-widest text-foreground/40 mb-4">
          维度评分
        </div>
        <DimensionScores dimensions={dimensions} compact={compact} />
      </div>

      {/* Focus Areas */}
      <div className="p-6 border-b border-[rgba(95,67,40,0.08)]">
        <div className="text-[10px] font-bold uppercase tracking-widest text-foreground/40 mb-4">
          专注领域
        </div>
        <FocusAreas areas={focusAreas} compact={compact} />
      </div>

      {/* Timeline */}
      {showTimeline && (
        <div className="p-6 border-b border-[rgba(95,67,40,0.08)]">
          <div className="text-[10px] font-bold uppercase tracking-widest text-foreground/40 mb-4">
            业绩时间线
          </div>
          <PerformanceTimeline events={timeline} compact={compact} />
        </div>
      )}

      {/* Recent Opinions */}
      {showOpinions && (
        <div className="p-6">
          <div className="text-[10px] font-bold uppercase tracking-widest text-foreground/40 mb-4">
            最近观点
          </div>
          <RecentOpinions opinions={recentOpinions} compact={compact} />
        </div>
      )}
    </div>
  );
}

// Helper component for metric blocks
function MetricBlock({
  label,
  value,
  subLabel,
  trend,
  icon
}: {
  label: string;
  value: string;
  subLabel?: string;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}) {
  const trendColors = {
    up: "text-emerald-600",
    down: "text-red-500",
    neutral: "text-foreground/70",
  };

  return (
    <div className="text-center">
      <div className="text-[9px] font-bold uppercase tracking-widest text-foreground/40 mb-1">
        {label}
      </div>
      <div className={cn(
        "text-xl font-bold tabular-nums flex items-center justify-center gap-1",
        trend ? trendColors[trend] : "text-foreground"
      )}>
        {icon}
        {value}
      </div>
      {subLabel && (
        <div className="text-[10px] text-foreground/50 mt-0.5">
          {subLabel}
        </div>
      )}
    </div>
  );
}

export default KOLRatingCard;