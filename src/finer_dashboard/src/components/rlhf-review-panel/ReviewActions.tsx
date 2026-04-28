"use client";

import React from "react";
import { Send, SkipForward, AlertTriangle, ChevronLeft, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ReviewActionsProps {
  onSubmit: () => void;
  onSkip: () => void;
  onFlag: () => void;
  onPrevious: () => void;
  canSubmit: boolean;
  canGoBack: boolean;
  isSubmitting: boolean;
  isFlagged: boolean;
  hasCorrections: boolean;
}

export function ReviewActions({
  onSubmit,
  onSkip,
  onFlag,
  onPrevious,
  canSubmit,
  canGoBack,
  isSubmitting,
  isFlagged,
  hasCorrections
}: ReviewActionsProps) {
  return (
    <div className="flex items-center gap-3">
      {/* Previous button */}
      <button
        onClick={onPrevious}
        disabled={!canGoBack}
        className={cn(
          "flex items-center gap-1.5 px-3 py-2 text-xs font-medium border rounded-sm transition-all",
          canGoBack
            ? "border-stone-200 text-foreground/70 hover:border-stone-300 hover:bg-stone-50"
            : "border-stone-100 text-stone-300 cursor-not-allowed"
        )}
      >
        <ChevronLeft className="w-3.5 h-3.5" />
        上一条
      </button>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Flag button */}
      <button
        onClick={onFlag}
        className={cn(
          "flex items-center gap-1.5 px-3 py-2 text-xs font-medium border rounded-sm transition-all",
          isFlagged
            ? "border-red-300 bg-red-50 text-red-700"
            : "border-stone-200 text-foreground/70 hover:border-red-200 hover:text-red-600 hover:bg-red-50"
        )}
      >
        <AlertTriangle className="w-3.5 h-3.5" />
        {isFlagged ? "已标记" : "标记异常"}
      </button>

      {/* Skip button */}
      <button
        onClick={onSkip}
        className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border border-stone-200 text-foreground/70 hover:border-stone-300 hover:bg-stone-50 rounded-sm transition-all"
      >
        <SkipForward className="w-3.5 h-3.5" />
        跳过
      </button>

      {/* Submit button */}
      <button
        onClick={onSubmit}
        disabled={!canSubmit || isSubmitting}
        className={cn(
          "flex items-center gap-1.5 px-5 py-2 text-xs font-bold uppercase tracking-wider rounded-sm transition-all",
          canSubmit && !isSubmitting
            ? "bg-morningstar-red text-white hover:bg-red-700 shadow-sm hover:shadow"
            : "bg-stone-200 text-stone-400 cursor-not-allowed"
        )}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            提交中...
          </>
        ) : (
          <>
            <Send className="w-3.5 h-3.5" />
            提交评价
            {hasCorrections && (
              <span className="text-[9px] bg-white/20 px-1.5 py-0.5 rounded ml-1">
                含修正
              </span>
            )}
          </>
        )}
      </button>
    </div>
  );
}