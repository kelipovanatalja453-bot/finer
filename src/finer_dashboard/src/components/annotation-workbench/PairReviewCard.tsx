"use client";

import React from "react";
import { Check, ChevronDown, ChevronRight, Code, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AnnotationEnums, PairReviewAnnotation, PairReviewItem } from "@/lib/contracts";
import { type DiffEntry, clearDraft, diffObjects, loadDraft, saveDraft } from "./annotation-helpers";

function pretty(jsonStr: string): string {
  try {
    return JSON.stringify(JSON.parse(jsonStr), null, 2);
  } catch {
    return jsonStr;
  }
}

function tryParse(jsonStr: string): Record<string, unknown> | null {
  try {
    const obj = JSON.parse(jsonStr);
    return typeof obj === "object" && obj !== null && !Array.isArray(obj) ? obj : null;
  } catch {
    return null;
  }
}

function formatValue(v: unknown): string {
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}

function isTypingTarget(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement | null;
  return (
    t instanceof HTMLInputElement ||
    t instanceof HTMLTextAreaElement ||
    t instanceof HTMLSelectElement ||
    Boolean(t?.isContentEditable)
  );
}

interface PairDraftState {
  verdict: string;
  editedChosen: string;
  notes: string;
}

function DiffView({ rejected, chosen }: { rejected: string; chosen: string }) {
  const rejObj = tryParse(rejected);
  const choObj = tryParse(chosen);
  const [showSame, setShowSame] = React.useState(false);

  if (!rejObj || !choObj) {
    return (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RawPane label="Rejected（基座原始输出）" json={rejected} color="red" />
        <RawPane label="Chosen（校准版 — 审这一侧）" json={chosen} color="green" />
      </div>
    );
  }

  const entries = diffObjects(rejObj, choObj);
  const changed = entries.filter((e) => e.type !== "same");
  const same = entries.filter((e) => e.type === "same");

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="border-b border-stone-100 px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-foreground/50">
        字段级差异 · {changed.length} 处不同 / {same.length} 处相同
      </div>
      <div className="divide-y divide-stone-100">
        {changed.map((entry) => (
          <DiffRow key={entry.key} entry={entry} />
        ))}

        {same.length > 0 && (
          <button
            onClick={() => setShowSame(!showSame)}
            className="flex w-full items-center gap-1.5 px-3 py-2 text-[11px] text-foreground/40 hover:bg-stone-50"
          >
            {showSame ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {same.length} 个相同字段
          </button>
        )}
        {showSame && same.map((entry) => (
          <DiffRow key={entry.key} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function DiffRow({ entry }: { entry: DiffEntry }) {
  const bgMap = {
    same: "bg-stone-50/50",
    changed: "bg-white",
    added: "bg-green-50/50",
    removed: "bg-red-50/50",
  };
  return (
    <div className={cn("px-3 py-2", bgMap[entry.type])}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px] font-semibold text-foreground/60">{entry.key}</span>
        {entry.type === "changed" && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-800">变更</span>}
        {entry.type === "added" && <span className="rounded bg-green-100 px-1.5 py-0.5 text-[9px] font-medium text-green-800">新增</span>}
        {entry.type === "removed" && <span className="rounded bg-red-100 px-1.5 py-0.5 text-[9px] font-medium text-red-800">删除</span>}
      </div>
      {entry.type === "changed" ? (
        <div className="mt-1 grid grid-cols-2 gap-2">
          <pre className="rounded bg-red-50 p-1.5 font-mono text-[10px] leading-relaxed text-red-800">{formatValue(entry.left)}</pre>
          <pre className="rounded bg-green-50 p-1.5 font-mono text-[10px] leading-relaxed text-green-800">{formatValue(entry.right)}</pre>
        </div>
      ) : entry.type === "same" ? (
        <pre className="mt-0.5 truncate font-mono text-[10px] text-foreground/30">{formatValue(entry.left)}</pre>
      ) : (
        <pre className="mt-1 rounded bg-stone-50 p-1.5 font-mono text-[10px] leading-relaxed text-foreground/70">
          {formatValue(entry.type === "added" ? entry.right : entry.left)}
        </pre>
      )}
    </div>
  );
}

function RawPane({ label, json, color }: { label: string; json: string; color: "red" | "green" }) {
  return (
    <div className={cn("rounded-lg border", color === "red" ? "border-red-200 bg-red-50/40" : "border-green-200 bg-green-50/40")}>
      <div className={cn("border-b px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider", color === "red" ? "border-red-100 text-red-700" : "border-green-100 text-green-700")}>
        {label}
      </div>
      <pre className="max-h-[32vh] overflow-auto p-3 font-mono text-[11px] leading-relaxed text-foreground/80">
        {pretty(json)}
      </pre>
    </div>
  );
}

export function PairReviewCard({
  item,
  enums,
  reviewerId,
  submitting,
  onSubmit,
}: {
  item: PairReviewItem;
  enums: AnnotationEnums;
  reviewerId: string;
  submitting: boolean;
  onSubmit: (annotation: PairReviewAnnotation) => void;
}) {
  const existing = item.annotation;
  const draftKey = item.pair_id;

  const savedDraft = React.useMemo(() => {
    if (existing) return null;
    return loadDraft<PairDraftState>("pairs_review", draftKey);
  }, [draftKey, existing]);

  const [verdict, setVerdict] = React.useState<PairReviewAnnotation["verdict"] | "">(
    (savedDraft?.verdict as PairReviewAnnotation["verdict"]) ?? existing?.verdict ?? "",
  );
  const [editedChosen, setEditedChosen] = React.useState(
    savedDraft?.editedChosen ?? existing?.edited_chosen ?? pretty(item.chosen),
  );
  const [notes, setNotes] = React.useState(savedDraft?.notes ?? existing?.notes ?? "");
  const [jsonError, setJsonError] = React.useState<string | null>(null);
  const [showRawFallback, setShowRawFallback] = React.useState(false);
  const mountTime = React.useRef(Date.now());

  // ── Draft persistence ───────────────────────────────────────────────────
  React.useEffect(() => {
    if (existing) return;
    saveDraft("pairs_review", draftKey, { verdict, editedChosen, notes } satisfies PairDraftState);
  }, [verdict, editedChosen, notes, draftKey, existing]);

  const canSubmit = verdict !== "" && reviewerId.trim().length > 0 && !submitting;

  const handleSubmit = React.useCallback(() => {
    if (!canSubmit) return;
    let edited: string | null = null;
    if (verdict === "edit") {
      try {
        edited = JSON.stringify(JSON.parse(editedChosen));
      } catch (e) {
        setJsonError(`JSON 不合法: ${e instanceof Error ? e.message : e}`);
        return;
      }
    }
    setJsonError(null);
    clearDraft("pairs_review", draftKey);
    onSubmit({
      pair_id: item.pair_id,
      reviewer_id: reviewerId.trim(),
      annotation_schema_version: enums.annotation_schema_version,
      verdict,
      edited_chosen: edited,
      notes: notes.trim() || null,
      duration_ms: Date.now() - mountTime.current,
    });
  }, [canSubmit, verdict, editedChosen, notes, item.pair_id, draftKey, reviewerId, enums.annotation_schema_version, onSubmit]);

  const formatEditedJson = React.useCallback(() => {
    try {
      setEditedChosen(JSON.stringify(JSON.parse(editedChosen), null, 2));
      setJsonError(null);
    } catch (e) {
      setJsonError(`JSON 格式错误: ${e instanceof Error ? e.message : e}`);
    }
  }, [editedChosen]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e) || e.metaKey || e.ctrlKey) return;
      const k = e.key.toLowerCase();
      if (k === "a") setVerdict("accept");
      if (k === "e") setVerdict("edit");
      if (k === "r") setVerdict("reject");
      if (e.key === "Enter") { e.preventDefault(); handleSubmit(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleSubmit]);

  return (
    <div className="space-y-4">
      {/* ── Diff view / raw toggle ─────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-1.5">
        <button
          onClick={() => setShowRawFallback(!showRawFallback)}
          className="flex items-center gap-1 rounded border border-stone-200 px-2 py-1 text-[10px] text-foreground/50 hover:bg-stone-50"
        >
          <Code className="h-3 w-3" />
          {showRawFallback ? "差异视图" : "原始 JSON"}
        </button>
      </div>

      {showRawFallback ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <RawPane label="Rejected（基座原始输出）" json={item.rejected} color="red" />
          <div className={cn("rounded-lg border", "border-green-200 bg-green-50/40")}>
            <div className="border-b border-green-100 px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-green-700">
              Chosen（校准版 — 审这一侧）
            </div>
            {verdict === "edit" ? (
              <textarea
                value={editedChosen}
                onChange={(e) => setEditedChosen(e.target.value)}
                spellCheck={false}
                className="h-[32vh] w-full resize-none bg-white p-3 font-mono text-[11px] leading-relaxed focus:outline-none"
              />
            ) : (
              <pre className="max-h-[32vh] overflow-auto p-3 font-mono text-[11px] leading-relaxed text-foreground/80">
                {pretty(item.chosen)}
              </pre>
            )}
          </div>
        </div>
      ) : verdict === "edit" ? (
        <div className="space-y-2">
          <DiffView rejected={item.rejected} chosen={item.chosen} />
          <div className="rounded-lg border border-amber-200 bg-amber-50/30">
            <div className="flex items-center justify-between border-b border-amber-100 px-3 py-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-amber-700">
                修正 Chosen
              </span>
              <button
                onClick={formatEditedJson}
                className="rounded border border-amber-200 px-2 py-0.5 text-[10px] text-amber-700 hover:bg-amber-100"
              >
                格式化
              </button>
            </div>
            <textarea
              value={editedChosen}
              onChange={(e) => setEditedChosen(e.target.value)}
              spellCheck={false}
              className="h-[24vh] w-full resize-none bg-white p-3 font-mono text-[11px] leading-relaxed focus:outline-none"
            />
          </div>
        </div>
      ) : (
        <DiffView rejected={item.rejected} chosen={item.chosen} />
      )}

      {jsonError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {jsonError}
        </div>
      )}

      {/* ── Verdict + submit ───────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setVerdict("accept")}
          className={cn(
            "flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
            verdict === "accept"
              ? "border-green-600 bg-green-600 text-white"
              : "border-stone-200 bg-white hover:bg-green-50",
          )}
        >
          <Check className="h-4 w-4" /> 合格 <kbd className="text-[9px] opacity-60">A</kbd>
        </button>
        <button
          onClick={() => setVerdict("edit")}
          className={cn(
            "flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
            verdict === "edit"
              ? "border-amber-500 bg-amber-500 text-white"
              : "border-stone-200 bg-white hover:bg-amber-50",
          )}
        >
          <Pencil className="h-4 w-4" /> 修正 chosen <kbd className="text-[9px] opacity-60">E</kbd>
        </button>
        <button
          onClick={() => setVerdict("reject")}
          className={cn(
            "flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
            verdict === "reject"
              ? "border-red-600 bg-red-600 text-white"
              : "border-stone-200 bg-white hover:bg-red-50",
          )}
        >
          <X className="h-4 w-4" /> 整对剔除 <kbd className="text-[9px] opacity-60">R</kbd>
        </button>

        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="备注（可选）"
          className="min-w-0 flex-1 rounded-md border border-stone-200 px-3 py-2 text-sm focus:border-stone-400 focus:outline-none"
        />
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={cn(
            "rounded-md px-5 py-2 text-sm font-medium transition-colors",
            canSubmit
              ? "bg-stone-800 text-white hover:bg-stone-700"
              : "cursor-not-allowed bg-stone-100 text-foreground/30",
          )}
        >
          {submitting ? "提交中..." : item.status === "annotated" ? "更新审核" : "保存并下一条"}
          <kbd className="ml-2 rounded bg-white/20 px-1 text-[9px]">⏎</kbd>
        </button>
      </div>
    </div>
  );
}
