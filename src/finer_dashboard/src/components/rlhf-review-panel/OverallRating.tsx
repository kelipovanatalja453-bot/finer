"use client";

import React from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OverallRatingProps {
  value: number;
  onChange: (rating: number) => void;
  disabled?: boolean;
}

const RATING_LABELS: Record<number, { short: string; full: string }> = {
  1: { short: "很差", full: "提取严重错误，完全不可用" },
  2: { short: "较差", full: "多处错误，需要大幅修正" },
  3: { short: "一般", full: "基本正确，有小问题" },
  4: { short: "良好", full: "提取准确，仅有细微瑕疵" },
  5: { short: "优秀", full: "完美提取，无需任何修改" }
};

export function OverallRating({ value, onChange, disabled }: OverallRatingProps) {
  const [hoveredRating, setHoveredRating] = React.useState(0);
  const displayRating = hoveredRating || value;
  const currentLabel = RATING_LABELS[value] || { short: "", full: "" };

  return (
    <div className={cn(
      "rounded-xl border border-[rgba(95,67,40,0.12)] bg-white/80 overflow-hidden transition-opacity",
      disabled && "opacity-50 pointer-events-none"
    )}>
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[rgba(95,67,40,0.08)] bg-[rgba(99,76,55,0.02)] flex items-center gap-2">
        <Star className="w-4 h-4 text-morningstar-red" strokeWidth={1.5} />
        <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/70">
          整体评价
        </h3>
        {value > 0 && (
          <span className="ml-auto text-xs font-medium text-morningstar-red">
            {value} 星
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <div className="flex items-center justify-center gap-1 mb-3">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              onClick={() => !disabled && onChange(star)}
              onMouseEnter={() => !disabled && setHoveredRating(star)}
              onMouseLeave={() => setHoveredRating(0)}
              className={cn(
                "p-1 transition-transform hover:scale-110",
                disabled && "cursor-not-allowed"
              )}
            >
              <Star
                className={cn(
                  "w-8 h-8 transition-colors",
                  star <= displayRating
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-stone-300"
                )}
                strokeWidth={star <= displayRating ? 0 : 1.5}
              />
            </button>
          ))}
        </div>

        <div className="text-center">
          {value > 0 ? (
            <>
              <div className="text-sm font-medium text-foreground">
                {currentLabel.short}
              </div>
              <div className="text-[11px] text-foreground/50 mt-0.5">
                {currentLabel.full}
              </div>
            </>
          ) : (
            <div className="text-sm text-foreground/40">
              点击星星评分 (或按 1-5 键)
            </div>
          )}
        </div>

        {/* Keyboard hint */}
        <div className="flex items-center justify-center gap-1 mt-3 text-[9px] text-foreground/30">
          {[1, 2, 3, 4, 5].map((num) => (
            <kbd
              key={num}
              className="px-1.5 py-0.5 bg-stone-100 border border-stone-200 rounded"
            >
              {num}
            </kbd>
          ))}
        </div>
      </div>
    </div>
  );
}