"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Award } from "lucide-react";

export interface StarRatingProps {
  rating: number; // 1-5
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  showMedal?: boolean;
  className?: string;
}

const RATING_CONFIG = {
  5: { label: "优秀", medal: "gold", medalColor: "text-amber-400" },
  4: { label: "良好", medal: "silver", medalColor: "text-slate-400" },
  3: { label: "一般", medal: "bronze", medalColor: "text-orange-600" },
  2: { label: "较差", medal: null, medalColor: "" },
  1: { label: "极差", medal: null, medalColor: "" },
} as const;

const SIZE_CONFIG = {
  sm: { star: "w-3 h-3", gap: "gap-0.5", text: "text-[10px]" },
  md: { star: "w-4 h-4", gap: "gap-1", text: "text-xs" },
  lg: { star: "w-5 h-5", gap: "gap-1.5", text: "text-sm" },
} as const;

export function StarRating({
  rating,
  size = "md",
  showLabel = false,
  showMedal = true,
  className,
}: StarRatingProps) {
  const clampedRating = Math.max(1, Math.min(5, Math.round(rating)));
  const config = RATING_CONFIG[clampedRating as keyof typeof RATING_CONFIG];
  const sizeConfig = SIZE_CONFIG[size];

  // Star color based on rating
  const getStarColor = (index: number) => {
    if (index < clampedRating) {
      if (clampedRating >= 5) return "text-amber-400 fill-amber-400";
      if (clampedRating >= 4) return "text-slate-400 fill-slate-400";
      if (clampedRating >= 3) return "text-orange-500 fill-orange-500";
      return "text-stone-400 fill-stone-400";
    }
    return "text-stone-200";
  };

  const medalStyle = getRatingMedalStyle(clampedRating);

  return (
    <div className={cn("flex items-center", sizeConfig.gap, className)}>
      {/* Medal Badge for 3+ stars */}
      {showMedal && medalStyle && (
        <div
          className={cn(
            "flex items-center justify-center w-6 h-6 rounded-full border shadow-sm",
            medalStyle.bg,
            medalStyle.border,
            medalStyle.shadow
          )}
        >
          <Award className={cn("w-3.5 h-3.5", medalStyle.icon)} strokeWidth={2.5} />
        </div>
      )}

      {/* Stars */}
      <div className={cn("flex items-center", sizeConfig.gap)}>
        {[0, 1, 2, 3, 4].map((index) => (
          <svg
            key={index}
            className={cn(sizeConfig.star, "transition-colors", getStarColor(index))}
            viewBox="0 0 24 24"
            fill={index < clampedRating ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth={2}
          >
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
          </svg>
        ))}
      </div>

      {/* Label */}
      {showLabel && (
        <span className={cn("font-medium text-foreground/70 ml-1", sizeConfig.text)}>
          {config.label}
        </span>
      )}
    </div>
  );
}

// Alternative: Compact medal-only display
export function MedalBadge({
  rating,
  size = "md",
}: {
  rating: number;
  size?: "sm" | "md" | "lg";
}) {
  const clampedRating = Math.max(1, Math.min(5, Math.round(rating)));
  const medalStyle = getRatingMedalStyle(clampedRating);

  if (!medalStyle || clampedRating < 3) {
    return (
      <div className={cn(
        "flex items-center justify-center rounded-full bg-stone-100 border border-stone-200",
        size === "sm" ? "w-5 h-5" : size === "lg" ? "w-8 h-8" : "w-6 h-6"
      )}>
        <span className={cn(
          "font-bold text-stone-400",
          size === "sm" ? "text-[8px]" : size === "lg" ? "text-sm" : "text-[10px]"
        )}>
          {clampedRating}
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full border shadow-sm",
        medalStyle.bg,
        medalStyle.border,
        medalStyle.shadow,
        size === "sm" ? "w-5 h-5" : size === "lg" ? "w-8 h-8" : "w-6 h-6"
      )}
    >
      <Award
        className={cn(
          medalStyle.icon,
          size === "sm" ? "w-2.5 h-2.5" : size === "lg" ? "w-5 h-5" : "w-3.5 h-3.5"
        )}
        strokeWidth={2.5}
      />
    </div>
  );
}

// Standalone medal style getter
export function getRatingMedalStyle(rating: number) {
  const clampedRating = Math.max(1, Math.min(5, Math.round(rating)));

  if (clampedRating === 5) {
    return {
      bg: "bg-gradient-to-br from-amber-100 to-amber-50",
      border: "border-amber-300",
      icon: "text-amber-500",
      shadow: "shadow-amber-200/30",
      label: "优秀",
    };
  }
  if (clampedRating === 4) {
    return {
      bg: "bg-gradient-to-br from-slate-100 to-slate-50",
      border: "border-slate-300",
      icon: "text-slate-500",
      shadow: "shadow-slate-200/30",
      label: "良好",
    };
  }
  if (clampedRating === 3) {
    return {
      bg: "bg-gradient-to-br from-orange-100 to-orange-50",
      border: "border-orange-300",
      icon: "text-orange-600",
      shadow: "shadow-orange-200/30",
      label: "一般",
    };
  }
  if (clampedRating === 2) {
    return {
      bg: "bg-stone-100",
      border: "border-stone-200",
      icon: "text-stone-400",
      shadow: "",
      label: "较差",
    };
  }
  return {
    bg: "bg-stone-100",
    border: "border-stone-200",
    icon: "text-stone-400",
    shadow: "",
    label: "极差",
  };
}

export default StarRating;