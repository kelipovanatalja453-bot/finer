"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { DimensionScore } from "./KOLRatingCard";

export interface DimensionScoresProps {
  dimensions: DimensionScore[];
  compact?: boolean;
  className?: string;
}

// Color scale: red (low) -> yellow (mid) -> green (high)
interface ScoreColorResult {
  ring: string;
  bg: string;
  text: string;
}

function getScoreColor(score: number): ScoreColorResult {
  if (score >= 80) return { ring: "#10b981", bg: "rgba(16, 185, 129, 0.1)", text: "text-emerald-600" };
  if (score >= 60) return { ring: "#eab308", bg: "rgba(234, 179, 8, 0.1)", text: "text-yellow-600" };
  if (score >= 40) return { ring: "#f97316", bg: "rgba(249, 115, 22, 0.1)", text: "text-orange-600" };
  return { ring: "#ef4444", bg: "rgba(239, 68, 68, 0.1)", text: "text-red-600" };
}

// Circular progress gauge
function GaugeIndicator({
  score,
  size = 64,
  strokeWidth = 4,
  label,
  weight,
  description,
}: {
  score: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  weight?: number;
  description?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;
  const color = getScoreColor(score);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Background circle */}
        <svg className="transform -rotate-90" width={size} height={size}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(0,0,0,0.05)"
            strokeWidth={strokeWidth}
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color.ring}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("text-lg font-bold tabular-nums", color.text)}>
            {score.toFixed(0)}
          </span>
        </div>
      </div>
      <div className="mt-2 text-center">
        <div className="text-xs font-bold text-foreground/80">{label}</div>
        {weight !== undefined && (
          <div className="text-[9px] text-foreground/40">
            权重 {(weight * 100).toFixed(0)}%
          </div>
        )}
      </div>
      {description && (
        <div className="text-[9px] text-foreground/40 mt-1 max-w-[80px] text-center leading-tight">
          {description}
        </div>
      )}
    </div>
  );
}

// Linear progress bar variant
function LinearIndicator({
  score,
  label,
  weight,
  description,
}: {
  score: number;
  label: string;
  weight?: number;
  description?: string;
}) {
  const color = getScoreColor(score);

  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-foreground/80">{label}</span>
          <div className="flex items-center gap-2">
            {weight !== undefined && (
              <span className="text-[9px] text-foreground/40">
                {(weight * 100).toFixed(0)}%
              </span>
            )}
            <span className={cn("text-sm font-bold tabular-nums", color.text)}>
              {score.toFixed(1)}
            </span>
          </div>
        </div>
        <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${score}%`,
              backgroundColor: color.ring,
            }}
          />
        </div>
        {description && (
          <div className="text-[9px] text-foreground/40 mt-1">{description}</div>
        )}
      </div>
    </div>
  );
}

export function DimensionScores({
  dimensions,
  compact = false,
  className,
}: DimensionScoresProps) {
  // Calculate weighted average
  const weightedAvg = dimensions.reduce((sum, d) => sum + d.score * (d.weight || 0), 0);

  if (compact) {
    return (
      <div className={cn("space-y-3", className)}>
        {dimensions.map((dim, index) => (
          <LinearIndicator
            key={index}
            score={dim.score}
            label={dim.name}
            weight={dim.weight}
            description={dim.description}
          />
        ))}
        {/* Weighted average */}
        <div className="pt-3 border-t border-[rgba(95,67,40,0.08)]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-foreground/60">综合得分</span>
            <span className="text-lg font-bold text-foreground tabular-nums">
              {weightedAvg.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("", className)}>
      {/* Gauges Grid */}
      <div className="flex flex-wrap justify-center gap-6 mb-6">
        {dimensions.map((dim, index) => (
          <GaugeIndicator
            key={index}
            score={dim.score}
            size={72}
            strokeWidth={5}
            label={dim.name}
            weight={dim.weight}
            description={dim.description}
          />
        ))}
      </div>

      {/* Weighted Average Summary */}
      <div className="flex items-center justify-center gap-3 p-4 rounded-xl bg-[rgba(95,67,40,0.04)] border border-[rgba(95,67,40,0.08)]">
        <span className="text-xs text-foreground/50">综合得分</span>
        <span className="text-2xl font-bold text-foreground tabular-nums">
          {weightedAvg.toFixed(1)}
        </span>
        <span className="text-xs text-foreground/40">/ 100</span>
      </div>
    </div>
  );
}

// Mini bar chart for compact view
export function DimensionMiniChart({
  dimensions,
  className,
}: {
  dimensions: DimensionScore[];
  className?: string;
}) {
  return (
    <div className={cn("flex items-end gap-1 h-8", className)}>
      {dimensions.map((dim, index) => {
        const height = (dim.score / 100) * 100;
        const color = getScoreColor(dim.score);

        return (
          <div
            key={index}
            className="flex-1 flex flex-col items-center group"
          >
            <div
              className="w-full rounded-t transition-all duration-300"
              style={{
                height: `${height}%`,
                backgroundColor: color.ring,
                opacity: 0.8,
              }}
            />
            <div className="opacity-0 group-hover:opacity-100 absolute -top-6 left-1/2 -translate-x-1/2 bg-black/80 text-white text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap transition-opacity">
              {dim.name}: {dim.score.toFixed(0)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default DimensionScores;