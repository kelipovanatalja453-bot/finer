"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  HelpCircle,
  RefreshCw,
  Undo2,
  User,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  AnnotationEnums,
  AnnotationExportMode,
  AnnotationExportResult,
  AnnotationItemStatus,
  AnnotationTaskId,
  AnnotationTaskSummary,
  ContextResponse,
  ContextResponseBlock,
  EvalAnnotationItem,
  EvalGoldAnnotation,
  PairReviewAnnotation,
  PairReviewItem,
} from "@/lib/contracts";
import { type DetectedEntity, detectEntities } from "./annotation-helpers";
import { AnnotationManual } from "./AnnotationManual";
import { EvidenceCard } from "./EvidenceCard";
import { EvalGoldForm } from "./EvalGoldForm";
import { MarketPanel } from "./MarketPanel";
import { PairReviewCard } from "./PairReviewCard";

const KOL_NOTE_CATEGORIES: { value: string; label: string }[] = [
  { value: "style", label: "投资风格" },
  { value: "discipline", label: "交易纪律" },
  { value: "preference", label: "偏好/行业" },
  { value: "track_record", label: "战绩/复盘" },
];

const CONTEXT_FETCH_SPAN = 20;
const CONTEXT_STEP = 3;

type AnyItem = EvalAnnotationItem | PairReviewItem;
type StatusFilter = AnnotationItemStatus | "";

function itemKey(taskId: AnnotationTaskId, item: AnyItem): string {
  return taskId === "eval_gold"
    ? (item as EvalAnnotationItem).id
    : (item as PairReviewItem).pair_id;
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

function errorMessage(body: Record<string, unknown>, fallback: string): string {
  const err = body?.error as Record<string, unknown> | undefined;
  const details = (err?.details ?? {}) as Record<string, unknown>;
  return `${err?.message ?? fallback}${details.fix_hint ? `（${details.fix_hint}）` : ""}`;
}

function statusLabel(status: AnnotationItemStatus): string {
  if (status === "excluded") return "已排除";
  return status === "annotated" ? "已标注" : "待标注";
}

// ── Quality panel ───────────────────────────────────────────────────────────

function QualityPanel({
  task,
  onRebuild,
  rebuildBusy,
  rebuildResult,
}: {
  task?: AnnotationTaskSummary;
  onRebuild: () => void;
  rebuildBusy: boolean;
  rebuildResult: string | null;
}) {
  if (!task) return null;
  const q = task.quality;
  const blocked = q.formal_blocking_reasons.length > 0;
  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            {blocked ? (
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-green-700" />
            )}
            任务准备 / 质量状态
          </div>
          <div className="mt-1 text-xs text-foreground/50">
            {task.source_path} → {task.export_path}
          </div>
        </div>
        {task.task_id === "eval_gold" && (
          <button
            onClick={onRebuild}
            disabled={rebuildBusy}
            className="flex items-center gap-1.5 rounded-md border border-stone-200 px-3 py-2 text-xs font-medium text-foreground/70 hover:bg-stone-50 disabled:opacity-50"
          >
            <Wrench className="h-3.5 w-3.5" />
            {rebuildBusy ? "重建中..." : "重建评测集"}
          </button>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <div className="rounded-md bg-stone-50 px-3 py-2">
          <div className="text-foreground/40">任务源</div>
          <div className="font-mono text-sm">{task.total}</div>
        </div>
        <div className="rounded-md bg-stone-50 px-3 py-2">
          <div className="text-foreground/40">已处理</div>
          <div className="font-mono text-sm">{task.annotated}</div>
        </div>
        <div className="rounded-md bg-stone-50 px-3 py-2">
          <div className="text-foreground/40">有效 gold</div>
          <div className="font-mono text-sm">{q.effective_gold_items}</div>
        </div>
        <div className="rounded-md bg-stone-50 px-3 py-2">
          <div className="text-foreground/40">排除/抽检</div>
          <div className="font-mono text-sm">
            {task.task_id === "eval_gold"
              ? q.excluded_items
              : `${q.pair_sample_reviewed ?? 0}/${q.pair_sample_size ?? 0}`}
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        {q.bad_source_lines > 0 && <span className="rounded bg-red-50 px-2 py-1 text-red-700">源坏行 {q.bad_source_lines}</span>}
        {q.bad_annotation_lines > 0 && <span className="rounded bg-red-50 px-2 py-1 text-red-700">标注坏行 {q.bad_annotation_lines}</span>}
        {q.dangling_annotations > 0 && <span className="rounded bg-amber-50 px-2 py-1 text-amber-800">悬空 {q.dangling_annotations}</span>}
        {q.legacy_missing_reviewer > 0 && <span className="rounded bg-amber-50 px-2 py-1 text-amber-800">旧标注 {q.legacy_missing_reviewer}</span>}
        {q.train_eval_overlap_ids.length > 0 && <span className="rounded bg-red-50 px-2 py-1 text-red-700">泄漏 {q.train_eval_overlap_ids.length}</span>}
        {q.unexcluded_image_placeholder_items > 0 && <span className="rounded bg-amber-50 px-2 py-1 text-amber-800">图片占位未排除 {q.unexcluded_image_placeholder_items}</span>}
        {q.unexcluded_weak_signal_items > 0 && <span className="rounded bg-amber-50 px-2 py-1 text-amber-800">弱信号未排除 {q.unexcluded_weak_signal_items}</span>}
      </div>

      {q.manifest_path && (
        <div className="mt-3 truncate border-t border-stone-100 pt-2 text-[11px] text-foreground/40">
          manifest: {q.manifest_path}
        </div>
      )}
      {rebuildResult && (
        <div className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800">
          {rebuildResult}
        </div>
      )}
      {blocked && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <div className="font-medium">Formal export 阻断</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {q.formal_blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

// ── KOL note modal ──────────────────────────────────────────────────────────

function KolNoteModal({
  initialText,
  initialCreator,
  sourceItemId,
  sourceFile,
  reviewerId,
  onClose,
  onSaved,
}: {
  initialText: string;
  initialCreator: string;
  sourceItemId: string;
  sourceFile: string;
  reviewerId: string;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const [text, setText] = React.useState(initialText);
  const [creator, setCreator] = React.useState(initialCreator);
  const [category, setCategory] = React.useState("style");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const save = React.useCallback(async () => {
    if (!text.trim() || !creator.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/annotation/kol-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          creator: creator.trim(),
          category,
          text: text.trim(),
          source_item_id: sourceItemId,
          source_file: sourceFile,
          reviewer_id: reviewerId,
        }),
      });
      const body = await res.json();
      if (body.ok) {
        onSaved(`已存入 ${body.data.path}（第 ${body.data.total_for_creator} 条）`);
        onClose();
      } else {
        setError(body.error?.message ?? "保存失败");
      }
    } catch {
      setError("无法连接后端");
    } finally {
      setBusy(false);
    }
  }, [text, creator, category, busy, sourceItemId, sourceFile, reviewerId, onSaved, onClose]);

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/30 px-4">
      <div className="w-full max-w-md rounded-lg border border-stone-200 bg-white p-5 shadow-xl">
        <div className="text-sm font-semibold">存入 KOL Profile</div>
        <div className="mt-1 text-xs text-foreground/50">
          速记追加到 data/kol_profiles/notes/{"{creator}"}.jsonl，KOL 页后续聚合
        </div>
        <div className="mt-3 flex gap-2">
          <input
            value={creator}
            onChange={(e) => setCreator(e.target.value)}
            placeholder="creator（如 maodaren）"
            className="w-40 rounded-md border border-stone-200 px-2 py-1.5 font-mono text-xs focus:border-stone-400 focus:outline-none"
          />
          <div className="flex flex-1 flex-wrap gap-1">
            {KOL_NOTE_CATEGORIES.map((c) => (
              <button
                key={c.value}
                onClick={() => setCategory(c.value)}
                className={cn(
                  "rounded-md border px-2 py-1 text-[11px]",
                  category === c.value
                    ? "border-stone-800 bg-stone-800 text-white"
                    : "border-stone-200 bg-white text-foreground/60 hover:bg-stone-50",
                )}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          className="mt-3 w-full rounded-md border border-stone-200 px-3 py-2 text-sm leading-relaxed focus:border-stone-400 focus:outline-none"
        />
        {error && <div className="mt-2 text-xs text-red-600">{error}</div>}
        <div className="mt-3 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-stone-200 px-3 py-2 text-xs text-foreground/60 hover:bg-stone-50"
          >
            取消
          </button>
          <button
            onClick={save}
            disabled={!text.trim() || !creator.trim() || busy}
            className="rounded-md bg-stone-900 px-4 py-2 text-xs font-medium text-white disabled:bg-stone-200"
          >
            {busy ? "保存中…" : "保存速记"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main workbench ──────────────────────────────────────────────────────────

export function AnnotationWorkbench() {
  const [tasks, setTasks] = React.useState<AnnotationTaskSummary[]>([]);
  const [enums, setEnums] = React.useState<AnnotationEnums | null>(null);
  const [activeTask, setActiveTask] = React.useState<AnnotationTaskId>("eval_gold");
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("pending");
  const [items, setItems] = React.useState<AnyItem[]>([]);
  const [index, setIndex] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [exporting, setExporting] = React.useState(false);
  const [rebuildBusy, setRebuildBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [exportResult, setExportResult] = React.useState<AnnotationExportResult | null>(null);
  const [rebuildResult, setRebuildResult] = React.useState<string | null>(null);
  const [reviewerId, setReviewerId] = React.useState("");
  const [reviewerDraft, setReviewerDraft] = React.useState("");
  const [editingReviewer, setEditingReviewer] = React.useState(false);
  const [manualOpen, setManualOpen] = React.useState(false);
  const [priceToFill, setPriceToFill] = React.useState<string | null>(null);
  const [undoToast, setUndoToast] = React.useState<{ key: string; idx: number } | null>(null);
  const undoTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // ── Context expansion state ─────────────────────────────────────────────
  const [contextData, setContextData] = React.useState<ContextResponse | null>(null);
  const [contextDepth, setContextDepth] = React.useState({ before: 0, after: 0 });
  const [contextIncluded, setContextIncluded] = React.useState<Map<number, ContextResponseBlock>>(new Map());
  const [contextLoading, setContextLoading] = React.useState(false);
  const [contextError, setContextError] = React.useState<string | null>(null);

  // ── KOL note modal + notice toast ───────────────────────────────────────
  const [kolNoteText, setKolNoteText] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const noticeTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const task = tasks.find((t) => t.task_id === activeTask);
  const item = items[index];

  const showNotice = React.useCallback((msg: string) => {
    clearTimeout(noticeTimer.current);
    setNotice(msg);
    noticeTimer.current = setTimeout(() => setNotice(null), 4000);
  }, []);
  const pairSampleSize = enums?.pair_sample_size ?? 30;
  const pairSampleSeed = enums?.pair_sample_seed ?? 20260610;
  const formalBlocked = Boolean(task?.quality.formal_blocking_reasons.length);

  // ── Entity detection for current item ───────────────────────────────────
  const detectedEntities: DetectedEntity[] = React.useMemo(() => {
    if (!item || !enums?.entity_aliases) return [];
    return detectEntities(item.evidence_text, enums.entity_aliases);
  }, [item, enums?.entity_aliases]);

  // ── Context expansion ───────────────────────────────────────────────────
  const currentItemId = item ? itemKey(activeTask, item) : null;

  React.useEffect(() => {
    // 切换条目时重置上下文状态
    setContextData(null);
    setContextDepth({ before: 0, after: 0 });
    setContextIncluded(new Map());
    setContextError(null);
    setPriceToFill(null);
  }, [currentItemId]);

  const expandContext = React.useCallback(
    async (side: "before" | "after") => {
      if (!currentItemId || activeTask !== "eval_gold") return;
      if (contextData) {
        setContextDepth((d) => ({ ...d, [side]: d[side] + CONTEXT_STEP }));
        return;
      }
      setContextLoading(true);
      setContextError(null);
      try {
        const res = await fetch(
          `/api/annotation/context?item_id=${encodeURIComponent(currentItemId)}&before=${CONTEXT_FETCH_SPAN}&after=${CONTEXT_FETCH_SPAN}`,
        );
        const body = await res.json();
        if (body.ok) {
          setContextData(body.data as ContextResponse);
          setContextDepth((d) => ({ ...d, [side]: CONTEXT_STEP }));
        } else {
          setContextError(errorMessage(body, "上下文加载失败"));
        }
      } catch {
        setContextError("上下文加载失败：无法连接后端");
      } finally {
        setContextLoading(false);
      }
    },
    [activeTask, contextData, currentItemId],
  );

  const contextBefore = React.useMemo(() => {
    if (!contextData) return [];
    return contextData.blocks
      .filter((b) => b.position === "before" && b.offset >= -contextDepth.before)
      .sort((a, b) => a.offset - b.offset);
  }, [contextData, contextDepth.before]);

  const contextAfter = React.useMemo(() => {
    if (!contextData) return [];
    return contextData.blocks
      .filter((b) => b.position === "after" && b.offset <= contextDepth.after)
      .sort((a, b) => a.offset - b.offset);
  }, [contextData, contextDepth.after]);

  const canExpandBefore = !contextData
    ? Boolean((item as EvalAnnotationItem | undefined)?.source_file)
    : contextData.blocks.some((b) => b.position === "before" && b.offset < -contextDepth.before);
  const canExpandAfter = !contextData
    ? Boolean((item as EvalAnnotationItem | undefined)?.source_file)
    : contextData.blocks.some((b) => b.position === "after" && b.offset > contextDepth.after);

  const toggleInclude = React.useCallback((block: ContextResponseBlock) => {
    setContextIncluded((prev) => {
      const next = new Map(prev);
      if (next.has(block.offset)) next.delete(block.offset);
      else next.set(block.offset, block);
      return next;
    });
  }, []);

  const includedContextBlocks = React.useMemo(
    () =>
      [...contextIncluded.values()]
        .sort((a, b) => a.offset - b.offset)
        .map((b) => ({ offset: b.offset, timestamp: b.timestamp ?? null, content: b.content })),
    [contextIncluded],
  );

  // ── Data fetching ───────────────────────────────────────────────────────
  const fetchTasks = React.useCallback(async () => {
    const res = await fetch("/api/annotation/tasks");
    const body = await res.json();
    if (body.ok) setTasks(body.data.tasks);
    else setError(errorMessage(body, "加载任务失败"));
  }, []);

  const fetchEnums = React.useCallback(async () => {
    const res = await fetch("/api/annotation/enums");
    const body = await res.json();
    if (body.ok) setEnums(body.data);
    else setError(errorMessage(body, "加载枚举失败"));
  }, []);

  const fetchItems = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ task_id: activeTask });
    if (statusFilter) params.set("status", statusFilter);
    if (activeTask === "pairs_review") {
      params.set("sample_size", String(pairSampleSize));
      params.set("seed", String(pairSampleSeed));
    }
    try {
      const res = await fetch(`/api/annotation/items?${params.toString()}`);
      const body = await res.json();
      if (body.ok) {
        setItems(body.data.items as AnyItem[]);
        setIndex(0);
      } else {
        setError(errorMessage(body, "加载条目失败"));
      }
    } catch {
      setError("无法连接后端");
    } finally {
      setLoading(false);
    }
  }, [activeTask, pairSampleSeed, pairSampleSize, statusFilter]);

  React.useEffect(() => {
    const saved = window.localStorage.getItem("finer.annotation.reviewer_id") ?? "";
    setReviewerId(saved);
    setReviewerDraft(saved);
    setEditingReviewer(!saved);
    fetchEnums().catch(() => setError("无法连接后端"));
    fetchTasks().catch(() => setError("无法连接后端"));
  }, [fetchEnums, fetchTasks]);

  React.useEffect(() => {
    setExportResult(null);
    fetchItems();
  }, [fetchItems]);

  // ── Navigation helpers ──────────────────────────────────────────────────
  const gotoNextPending = React.useCallback(() => {
    for (let step = 1; step <= items.length; step++) {
      const next = (index + step) % items.length;
      if (items[next].status === "pending") {
        setIndex(next);
        return;
      }
    }
  }, [index, items]);

  const saveReviewer = React.useCallback(() => {
    const value = reviewerDraft.trim();
    if (!value) return;
    window.localStorage.setItem("finer.annotation.reviewer_id", value);
    setReviewerId(value);
    setEditingReviewer(false);
  }, [reviewerDraft]);

  // ── Submit with optimistic update ───────────────────────────────────────
  const handleSubmit = React.useCallback(
    async (annotation: EvalGoldAnnotation | PairReviewAnnotation) => {
      setSubmitting(true);
      setError(null);
      const currentKey = item ? itemKey(activeTask, item) : "";
      const currentIndex = index;
      try {
        const res = await fetch("/api/annotation/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: activeTask, annotation }),
        });
        const body = await res.json();
        if (!body.ok) {
          setError(errorMessage(body, "提交失败"));
          return;
        }

        // Optimistic: update local item
        const newStatus: AnnotationItemStatus =
          activeTask === "eval_gold" && (annotation as EvalGoldAnnotation).sample_verdict === "exclude"
            ? "excluded"
            : "annotated";
        setItems((prev) =>
          prev.map((it, i) =>
            i === currentIndex ? ({ ...it, status: newStatus, annotation } as AnyItem) : it,
          ),
        );

        // Update task summary from response
        if (body.data?.progress) {
          setTasks((prev) =>
            prev.map((t) => (t.task_id === activeTask ? body.data.progress : t)),
          );
        }

        // Undo toast
        clearTimeout(undoTimer.current);
        setUndoToast({ key: currentKey, idx: currentIndex });
        undoTimer.current = setTimeout(() => setUndoToast(null), 5000);

        // Advance to next pending
        // Use a small delay so the state update from setItems settles
        requestAnimationFrame(() => {
          gotoNextPending();
        });

        // Background refresh for accuracy
        fetchTasks().catch(() => {});
      } catch {
        setError("提交失败：无法连接后端");
      } finally {
        setSubmitting(false);
      }
    },
    [activeTask, fetchTasks, gotoNextPending, index, item],
  );

  // ── Export ──────────────────────────────────────────────────────────────
  const handleExport = React.useCallback(
    async (mode: AnnotationExportMode) => {
      setExporting(true);
      setError(null);
      try {
        const res = await fetch("/api/annotation/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: activeTask, mode }),
        });
        const body = await res.json();
        if (body.ok) setExportResult(body.data);
        else setError(errorMessage(body, "导出失败"));
        await fetchTasks();
      } catch {
        setError("导出失败：无法连接后端");
      } finally {
        setExporting(false);
      }
    },
    [activeTask, fetchTasks],
  );

  // ── Rebuild ─────────────────────────────────────────────────────────────
  const handleRebuild = React.useCallback(async () => {
    setRebuildBusy(true);
    setError(null);
    setRebuildResult(null);
    try {
      const res = await fetch("/api/annotation/eval-source/rebuild", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const body = await res.json();
      if (body.ok) {
        setRebuildResult(`已重建 ${body.data.selected} 条评测任务源 → ${body.data.source_path}`);
        setStatusFilter("pending");
        await fetchTasks();
        await fetchItems();
      } else {
        setError(errorMessage(body, "重建失败"));
      }
    } catch {
      setError("重建失败：无法连接后端");
    } finally {
      setRebuildBusy(false);
    }
  }, [fetchItems, fetchTasks]);

  // ── Keyboard: ← → S ? ──────────────────────────────────────────────────
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e) || e.metaKey || e.ctrlKey) return;
      if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
      if (e.key === "ArrowRight") setIndex((i) => Math.min(items.length - 1, i + 1));
      if (e.key.toLowerCase() === "s") gotoNextPending();
      if (e.key === "?" || e.key === "／") {
        e.preventDefault();
        setManualOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [gotoNextPending, items.length]);

  // ── Entity click → ticker fill ──────────────────────────────────────────
  const [tickerToFill, setTickerToFill] = React.useState<string | null>(null);

  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-6">
      {/* ── Manual drawer ──────────────────────────────────────────────── */}
      {manualOpen && <AnnotationManual onClose={() => setManualOpen(false)} />}

      {/* ── KOL note modal ─────────────────────────────────────────────── */}
      {kolNoteText !== null && item && (
        <KolNoteModal
          initialText={kolNoteText}
          initialCreator={item.creator && item.creator !== "unknown" ? item.creator : ""}
          sourceItemId={itemKey(activeTask, item)}
          sourceFile={item.source_file ?? ""}
          reviewerId={reviewerId}
          onClose={() => setKolNoteText(null)}
          onSaved={showNotice}
        />
      )}

      {/* ── Notice toast ───────────────────────────────────────────────── */}
      {notice && (
        <div className="fixed bottom-16 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-xs text-green-800 shadow-lg">
          {notice}
        </div>
      )}

      {/* ── Reviewer identity modal ────────────────────────────────────── */}
      {editingReviewer && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/30 px-4">
          <div className="w-full max-w-sm rounded-lg border border-stone-200 bg-white p-5 shadow-xl">
            <div className="text-sm font-semibold">标注者身份</div>
            <div className="mt-1 text-xs text-foreground/50">
              reviewer_id 会写入每条标注，用于 formal export 审计。
            </div>
            <input
              autoFocus
              value={reviewerDraft}
              onChange={(e) => setReviewerDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") saveReviewer(); }}
              placeholder="如 analyst_zhang"
              className="mt-4 w-full rounded-md border border-stone-200 px-3 py-2 font-mono text-sm focus:border-stone-400 focus:outline-none"
            />
            <button
              onClick={saveReviewer}
              disabled={!reviewerDraft.trim()}
              className="mt-3 w-full rounded-md bg-stone-900 px-3 py-2 text-sm font-medium text-white disabled:bg-stone-200"
            >
              保存 reviewer_id
            </button>
          </div>
        </div>
      )}

      {/* ── Top bar: task tabs + actions ────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {tasks.map((t) => (
            <button
              key={t.task_id}
              onClick={() => { setActiveTask(t.task_id); setStatusFilter("pending"); }}
              className={cn(
                "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                activeTask === t.task_id
                  ? "border-stone-800 bg-stone-800 text-white"
                  : "border-stone-200 bg-white text-foreground/70 hover:bg-stone-50",
              )}
            >
              {t.title}
              <span className="ml-2 text-xs opacity-60">{t.annotated}/{t.total}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setManualOpen(true)}
            className="flex items-center gap-1 rounded-md border border-stone-200 bg-white px-2.5 py-2 text-xs text-foreground/60 hover:bg-stone-50"
            title="标注手册 (?)"
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setEditingReviewer(true)}
            className="flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-2 text-xs text-foreground/60 hover:bg-stone-50"
          >
            <User className="h-3.5 w-3.5" />
            {reviewerId || "设置 reviewer"}
          </button>
          <button
            onClick={() => { fetchTasks(); fetchItems(); }}
            className="flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-2 text-xs text-foreground/60 hover:bg-stone-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> 刷新
          </button>
          <button
            onClick={() => handleExport("formal")}
            disabled={formalBlocked || exporting}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium",
              !formalBlocked
                ? "bg-morningstar-red text-white hover:opacity-90"
                : "cursor-not-allowed bg-stone-100 text-foreground/30",
            )}
          >
            <Download className="h-3.5 w-3.5" />
            Formal 导出
          </button>
          <button
            onClick={() => handleExport("draft")}
            disabled={exporting}
            className="rounded-md border border-stone-200 bg-white px-3 py-2 text-xs text-foreground/50 hover:bg-stone-50"
          >
            Draft
          </button>
        </div>
      </div>

      {/* ── Quality panel ──────────────────────────────────────────────── */}
      <QualityPanel
        task={task}
        onRebuild={handleRebuild}
        rebuildBusy={rebuildBusy}
        rebuildResult={activeTask === "eval_gold" ? rebuildResult : null}
      />

      {/* ── Status filter bar ──────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 bg-white px-3 py-2">
        <div className="flex flex-wrap gap-1.5">
          {(["pending", "annotated", "excluded", ""] as StatusFilter[]).map((status) => {
            if (activeTask === "pairs_review" && status === "excluded") return null;
            const label = status ? statusLabel(status) : "全部";
            return (
              <button
                key={status || "all"}
                onClick={() => setStatusFilter(status)}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-xs",
                  statusFilter === status
                    ? "bg-stone-900 text-white"
                    : "bg-stone-50 text-foreground/60 hover:bg-stone-100",
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
        {activeTask === "pairs_review" && (
          <div className="text-xs text-foreground/45">
            抽样队列 seed={pairSampleSeed} / n={pairSampleSize}
          </div>
        )}
      </div>

      {/* ── Progress bar ───────────────────────────────────────────────── */}
      {task && task.total > 0 && (
        <div className="h-1 overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full bg-morningstar-red transition-all duration-300"
            style={{ width: `${(task.annotated / task.total) * 100}%` }}
          />
        </div>
      )}

      {/* ── Export result banner ────────────────────────────────────────── */}
      {exportResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm">
          <div className="font-medium text-green-800">
            已导出 {exportResult.exported} 条 → {exportResult.export_path}
            <span className="ml-2 font-mono text-xs opacity-60">mode={exportResult.mode}</span>
          </div>
          {exportResult.expected_abstain_count != null && (
            <div className="mt-1 text-xs text-green-700">
              弃权 {exportResult.expected_abstain_count} / 排除 {exportResult.excluded ?? 0}
            </div>
          )}
          {exportResult.unreviewed != null && (
            <div className="mt-1 text-xs text-green-700">
              合格 {exportResult.accept} / 修正 {exportResult.edit} / 剔除 {exportResult.reject} / 未审 {exportResult.unreviewed}
            </div>
          )}
        </div>
      )}

      {/* ── Error banner ───────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ── Undo toast ─────────────────────────────────────────────────── */}
      {undoToast && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-stone-200 bg-white px-4 py-2.5 shadow-lg">
          <div className="flex items-center gap-3 text-sm">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <span className="text-foreground/70">已保存 <span className="font-mono text-[11px]">{undoToast.key}</span></span>
            <button
              onClick={() => { setIndex(undoToast.idx); setUndoToast(null); }}
              className="flex items-center gap-1 rounded border border-stone-200 px-2 py-1 text-xs text-foreground/60 hover:bg-stone-50"
            >
              <Undo2 className="h-3 w-3" /> 跳回
            </button>
            <button
              onClick={() => setUndoToast(null)}
              className="text-xs text-foreground/30 hover:text-foreground/50"
            >
              关闭
            </button>
          </div>
        </div>
      )}

      {/* ── Main content area ──────────────────────────────────────────── */}
      {loading || !enums ? (
        <div className="py-24 text-center text-sm text-foreground/40">加载中...</div>
      ) : !task?.ready ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-6">
          <div className="text-sm font-medium text-amber-900">任务源未就绪</div>
          <div className="mt-2 text-xs text-amber-800">{task?.fix_hint}</div>
        </div>
      ) : !item ? (
        <div className="py-24 text-center text-sm text-foreground/40">当前筛选下没有条目</div>
      ) : (
        <div className="space-y-4">
          {/* ── Pagination ─────────────────────────────────────────────── */}
          <div className="flex items-center justify-between text-xs text-foreground/50">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
                disabled={index === 0}
                className="rounded border border-stone-200 p-1 disabled:opacity-30"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <span className="font-mono">
                {index + 1} / {items.length}
              </span>
              <button
                onClick={() => setIndex((i) => Math.min(items.length - 1, i + 1))}
                disabled={index === items.length - 1}
                className="rounded border border-stone-200 p-1 disabled:opacity-30"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-medium",
                  item.status === "annotated"
                    ? "bg-green-100 text-green-700"
                    : item.status === "excluded"
                      ? "bg-red-100 text-red-700"
                      : "bg-stone-100 text-foreground/50",
                )}
              >
                {statusLabel(item.status)}
              </span>
              <span className="font-mono text-[10px] text-foreground/30">
                {itemKey(activeTask, item)}
              </span>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <kbd className="rounded border border-stone-200 bg-stone-100 px-1.5 py-0.5 text-[9px]">←/→</kbd>
              导航
              <kbd className="rounded border border-stone-200 bg-stone-100 px-1.5 py-0.5 text-[9px]">S</kbd>
              下一条待标
              <kbd className="rounded border border-stone-200 bg-stone-100 px-1.5 py-0.5 text-[9px]">?</kbd>
              手册
            </div>
          </div>

          {/* ── Sticky split: evidence left, form right ────────────────── */}
          <div className="lg:flex lg:items-start lg:gap-5">
            <div className="space-y-3 lg:sticky lg:top-4 lg:w-[42%] lg:shrink-0">
              <EvidenceCard
                text={item.evidence_text}
                sourceFile={item.source_file}
                creator={item.creator}
                timestamp={(item as EvalAnnotationItem).timestamp}
                detectedEntities={detectedEntities}
                onNumberClick={activeTask === "eval_gold" ? setPriceToFill : undefined}
                onEntityClick={activeTask === "eval_gold" ? setTickerToFill : undefined}
                contextBefore={activeTask === "eval_gold" ? contextBefore : undefined}
                contextAfter={activeTask === "eval_gold" ? contextAfter : undefined}
                canExpandBefore={activeTask === "eval_gold" ? canExpandBefore : false}
                canExpandAfter={activeTask === "eval_gold" ? canExpandAfter : false}
                contextLoading={contextLoading}
                contextError={contextError}
                onExpandBefore={activeTask === "eval_gold" ? () => expandContext("before") : undefined}
                onExpandAfter={activeTask === "eval_gold" ? () => expandContext("after") : undefined}
                includedOffsets={new Set(contextIncluded.keys())}
                onToggleInclude={activeTask === "eval_gold" ? toggleInclude : undefined}
                onSaveSelection={(text) => setKolNoteText(text)}
              />
              {activeTask === "eval_gold" && (
                <MarketPanel
                  entities={detectedEntities}
                  anchorDate={(item as EvalAnnotationItem).timestamp}
                />
              )}
            </div>
            <div className="mt-4 min-w-0 flex-1 lg:mt-0">
              {activeTask === "eval_gold" ? (
                <EvalGoldForm
                  key={itemKey(activeTask, item)}
                  item={item as EvalAnnotationItem}
                  enums={enums}
                  reviewerId={reviewerId}
                  submitting={submitting}
                  onSubmit={handleSubmit}
                  detectedEntities={detectedEntities}
                  priceToFill={priceToFill}
                  onPriceConsumed={() => setPriceToFill(null)}
                  tickerToFill={tickerToFill}
                  onTickerConsumed={() => setTickerToFill(null)}
                  contextBlocks={includedContextBlocks}
                />
              ) : (
                <PairReviewCard
                  key={itemKey(activeTask, item)}
                  item={item as PairReviewItem}
                  enums={enums}
                  reviewerId={reviewerId}
                  submitting={submitting}
                  onSubmit={handleSubmit}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
