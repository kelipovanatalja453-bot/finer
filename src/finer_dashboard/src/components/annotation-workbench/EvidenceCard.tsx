"use client";

import React from "react";
import { BookmarkPlus, ChevronDown, ChevronUp, FileText, Loader2, Tag, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ContextResponseBlock } from "@/lib/contracts";
import type { DetectedEntity } from "./annotation-helpers";

/** 数字高亮渲染；onNumberClick 存在时数字可点击填入价位。 */
function MarkedText({
  text,
  onNumberClick,
}: {
  text: string;
  onNumberClick?: (value: string) => void;
}) {
  const parts = React.useMemo(() => text.split(/(\d+(?:\.\d+)?%?)/g), [text]);
  return (
    <>
      {parts.map((part, i) =>
        /^\d/.test(part) ? (
          <mark
            key={i}
            role={onNumberClick ? "button" : undefined}
            tabIndex={onNumberClick ? 0 : undefined}
            onClick={() => onNumberClick?.(part.replace(/%$/, ""))}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onNumberClick?.(part.replace(/%$/, ""));
            }}
            className={
              "rounded-sm bg-amber-100 px-0.5 font-semibold text-amber-900" +
              (onNumberClick
                ? " cursor-pointer transition-colors hover:bg-amber-200 active:bg-amber-300"
                : "")
            }
            title={onNumberClick ? `点击填入价位 ${part}` : undefined}
          >
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}

function ContextBlockRow({
  block,
  included,
  onToggleInclude,
  onNumberClick,
}: {
  block: ContextResponseBlock;
  included: boolean;
  onToggleInclude?: (block: ContextResponseBlock) => void;
  onNumberClick?: (value: string) => void;
}) {
  return (
    <div
      className={cn(
        "group border-l-2 px-3 py-1.5 text-xs leading-relaxed transition-colors",
        included
          ? "border-amber-400 bg-amber-50/60 text-foreground/85"
          : "border-stone-200 bg-stone-50/60 text-foreground/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 whitespace-pre-wrap">
          {included ? (
            <MarkedText text={block.content} onNumberClick={onNumberClick} />
          ) : (
            block.content || <span className="italic opacity-50">（空消息）</span>
          )}
        </div>
        {onToggleInclude && (
          <button
            type="button"
            onClick={() => onToggleInclude(block)}
            className={cn(
              "shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium transition-colors",
              included
                ? "border-amber-400 bg-amber-100 text-amber-800"
                : "border-stone-200 bg-white text-foreground/40 opacity-0 group-hover:opacity-100 hover:bg-stone-50",
            )}
            title={included ? "从证据中移除" : "并入证据（导出时拼进 eval 样本）"}
          >
            {included ? "已并入 ✓" : "并入证据"}
          </button>
        )}
      </div>
      {block.timestamp && (
        <div className="mt-0.5 text-[9px] text-foreground/30">{block.timestamp}</div>
      )}
    </div>
  );
}

export function EvidenceCard({
  text,
  sourceFile,
  creator,
  timestamp,
  detectedEntities,
  onNumberClick,
  onEntityClick,
  contextBefore,
  contextAfter,
  canExpandBefore,
  canExpandAfter,
  contextLoading,
  contextError,
  onExpandBefore,
  onExpandAfter,
  includedOffsets,
  onToggleInclude,
  onSaveSelection,
}: {
  text: string;
  sourceFile?: string | null;
  creator?: string | null;
  timestamp?: string | null;
  detectedEntities?: DetectedEntity[];
  onNumberClick?: (value: string) => void;
  onEntityClick?: (ticker: string) => void;
  /** 已加载且当前可见的上文块（offset 升序） */
  contextBefore?: ContextResponseBlock[];
  contextAfter?: ContextResponseBlock[];
  canExpandBefore?: boolean;
  canExpandAfter?: boolean;
  contextLoading?: boolean;
  contextError?: string | null;
  onExpandBefore?: () => void;
  onExpandAfter?: () => void;
  includedOffsets?: Set<number>;
  onToggleInclude?: (block: ContextResponseBlock) => void;
  /** 文本选区 → KOL 速记 */
  onSaveSelection?: (text: string) => void;
}) {
  const [selText, setSelText] = React.useState("");

  const handleMouseUp = React.useCallback(() => {
    if (!onSaveSelection) return;
    const sel = window.getSelection()?.toString().trim() ?? "";
    setSelText(sel.length >= 4 ? sel : "");
  }, [onSaveSelection]);

  const included = includedOffsets ?? new Set<number>();

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex items-center justify-between border-b border-stone-100 px-4 py-2">
        <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-foreground/50">
          <FileText className="h-3 w-3" />
          原文证据
          {included.size > 0 && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium normal-case tracking-normal text-amber-800">
              +{included.size} 条上下文已并入
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-foreground/40">
          {creator && <span>{creator}</span>}
          {timestamp && <span>{timestamp}</span>}
        </div>
      </div>

      {detectedEntities && detectedEntities.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 border-b border-stone-100 px-4 py-2">
          <Tag className="h-3 w-3 shrink-0 text-foreground/30" />
          {detectedEntities.map((e) => (
            <button
              key={e.ticker}
              type="button"
              onClick={() => onEntityClick?.(e.ticker)}
              className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-medium text-blue-700 transition-colors hover:bg-blue-100"
              title={`点击填入 ${e.ticker}`}
            >
              {e.alias} → {e.ticker}
              <span className="ml-1 text-[9px] opacity-50">{e.market}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Selection action bar ─────────────────────────────────────── */}
      {selText && onSaveSelection && (
        <div className="flex items-center justify-between gap-2 border-b border-blue-100 bg-blue-50/70 px-4 py-1.5">
          <span className="min-w-0 truncate text-[11px] text-blue-800">
            已选中 {selText.length} 字：「{selText.slice(0, 30)}{selText.length > 30 ? "…" : ""}」
          </span>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => { onSaveSelection(selText); setSelText(""); }}
              className="flex items-center gap-1 rounded border border-blue-300 bg-white px-2 py-0.5 text-[10px] font-medium text-blue-700 hover:bg-blue-100"
            >
              <BookmarkPlus className="h-3 w-3" /> 存入 KOL Profile
            </button>
            <button
              type="button"
              onClick={() => setSelText("")}
              className="rounded p-0.5 text-blue-400 hover:text-blue-600"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      <div onMouseUp={handleMouseUp} className="max-h-[46vh] overflow-y-auto lg:max-h-[calc(100vh-22rem)]">
        {/* ── Expand-before + context blocks ─────────────────────────── */}
        {onExpandBefore && (canExpandBefore || contextLoading) && (
          <button
            type="button"
            onClick={onExpandBefore}
            disabled={contextLoading}
            className="flex w-full items-center justify-center gap-1 border-b border-dashed border-stone-200 py-1 text-[10px] text-foreground/40 hover:bg-stone-50 hover:text-foreground/60 disabled:opacity-50"
          >
            {contextLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ChevronUp className="h-3 w-3" />}
            展开上文
          </button>
        )}
        {contextBefore?.map((block) => (
          <ContextBlockRow
            key={block.offset}
            block={block}
            included={included.has(block.offset)}
            onToggleInclude={onToggleInclude}
            onNumberClick={onNumberClick}
          />
        ))}

        {/* ── Main evidence ───────────────────────────────────────────── */}
        <div className="whitespace-pre-wrap p-4 text-sm leading-relaxed text-foreground/90">
          <MarkedText text={text} onNumberClick={onNumberClick} />
        </div>

        {/* ── Context blocks after + expand-after ────────────────────── */}
        {contextAfter?.map((block) => (
          <ContextBlockRow
            key={block.offset}
            block={block}
            included={included.has(block.offset)}
            onToggleInclude={onToggleInclude}
            onNumberClick={onNumberClick}
          />
        ))}
        {onExpandAfter && (canExpandAfter || contextLoading) && (
          <button
            type="button"
            onClick={onExpandAfter}
            disabled={contextLoading}
            className="flex w-full items-center justify-center gap-1 border-t border-dashed border-stone-200 py-1 text-[10px] text-foreground/40 hover:bg-stone-50 hover:text-foreground/60 disabled:opacity-50"
          >
            {contextLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ChevronDown className="h-3 w-3" />}
            展开下文
          </button>
        )}
      </div>

      {contextError && (
        <div className="border-t border-amber-100 bg-amber-50/60 px-4 py-1.5 text-[10px] text-amber-700">
          {contextError}
        </div>
      )}

      {sourceFile && (
        <div className="truncate border-t border-stone-100 px-4 py-1.5 text-[10px] text-foreground/30">
          {sourceFile}
        </div>
      )}
    </div>
  );
}
