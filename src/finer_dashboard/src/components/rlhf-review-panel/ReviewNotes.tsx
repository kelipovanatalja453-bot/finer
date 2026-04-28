"use client";

import React from "react";
import { MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ReviewNotesProps {
  value: string;
  onChange: (notes: string) => void;
  placeholder?: string;
  maxLength?: number;
}

export function ReviewNotes({
  value,
  onChange,
  placeholder = "添加备注...",
  maxLength = 500
}: ReviewNotesProps) {
  const charCount = value.length;
  const isNearLimit = charCount > maxLength * 0.8;
  const isAtLimit = charCount >= maxLength;

  return (
    <div className="rounded-xl border border-[rgba(95,67,40,0.12)] bg-white/80 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[rgba(95,67,40,0.08)] bg-[rgba(99,76,55,0.02)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-morningstar-red" strokeWidth={1.5} />
          <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/70">
            备注说明
          </h3>
        </div>

        <span className={cn(
          "text-[10px] font-medium transition-colors",
          isAtLimit
            ? "text-red-600"
            : isNearLimit
              ? "text-amber-600"
              : "text-foreground/40"
        )}>
          {charCount}/{maxLength}
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
        <textarea
          value={value}
          onChange={(e) => {
            if (e.target.value.length <= maxLength) {
              onChange(e.target.value);
            }
          }}
          placeholder={placeholder}
          rows={4}
          className={cn(
            "w-full px-3 py-2 text-sm bg-white/50 border border-stone-200 rounded-sm resize-none",
            "placeholder:text-foreground/30",
            "focus:border-morningstar-red focus:ring-1 focus:ring-morningstar-red/20 focus:bg-white",
            "outline-none transition-all"
          )}
        />

        {/* Quick notes */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          <span className="text-[10px] text-foreground/40 mr-1">快捷输入:</span>
          {[
            "标注正确",
            "方向修正",
            "代码有误",
            "操作链不全",
            "需要二次确认"
          ].map((quickNote) => (
            <button
              key={quickNote}
              onClick={() => {
                const newValue = value ? `${value}; ${quickNote}` : quickNote;
                if (newValue.length <= maxLength) {
                  onChange(newValue);
                }
              }}
              disabled={value.length + quickNote.length + 2 > maxLength}
              className={cn(
                "px-2 py-0.5 text-[10px] font-medium rounded-full border transition-all",
                value.length + quickNote.length + 2 > maxLength
                  ? "border-stone-100 text-stone-300 cursor-not-allowed"
                  : "border-stone-200 text-foreground/60 hover:border-morningstar-red/30 hover:text-morningstar-red hover:bg-red-50"
              )}
            >
              {quickNote}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}