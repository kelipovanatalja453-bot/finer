"use client";

import React from "react";
import { FileText, Calendar, Highlighter } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OriginalTextCardProps {
  text: string;
  sourceFile: string;
  extractedAt: string;
  highlightedText?: string | null;
}

export function OriginalTextCard({
  text,
  sourceFile,
  extractedAt,
  highlightedText
}: OriginalTextCardProps) {
  // Render text with highlighted portion
  const renderHighlighted = () => {
    if (!highlightedText || !text.includes(highlightedText)) {
      return <span className="text-foreground/80">{text}</span>;
    }

    const parts = text.split(highlightedText);
    return (
      <>
        <span className="text-foreground/80">{parts[0]}</span>
        <mark className="bg-yellow-200 text-foreground px-0.5 rounded">
          {highlightedText}
        </mark>
        <span className="text-foreground/80">{parts.slice(1).join(highlightedText)}</span>
      </>
    );
  };

  return (
    <div className="rounded-xl border border-[rgba(95,67,40,0.12)] bg-white/80 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-[rgba(95,67,40,0.08)] bg-[rgba(99,76,55,0.02)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-morningstar-red" strokeWidth={1.5} />
          <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/70">
            原文内容
          </h3>
        </div>

        {highlightedText && (
          <div className="flex items-center gap-1.5 text-[10px] text-yellow-700 bg-yellow-50 px-2 py-1 rounded-full">
            <Highlighter className="w-3 h-3" />
            <span className="font-medium">高亮模式</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-5">
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {renderHighlighted()}
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-[rgba(95,67,40,0.08)] bg-[rgba(99,76,55,0.02)] flex items-center gap-4 text-[10px] text-foreground/50">
        <div className="flex items-center gap-1.5">
          <FileText className="w-3 h-3" strokeWidth={1.5} />
          <span className="font-mono truncate max-w-xs">{sourceFile}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <Calendar className="w-3 h-3" strokeWidth={1.5} />
          <span>{extractedAt}</span>
        </div>
      </div>
    </div>
  );
}