"use client";

import React from "react";
import { AlertTriangle, Ban, CheckCircle2, Plus, Sparkles, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  AnnotationEnums,
  ContextBlock,
  EvalAnnotationItem,
  EvalGoldAnnotation,
  EvalSampleVerdict,
  GoldActionStep,
  GoldExtraction,
} from "@/lib/contracts";
import {
  type DetectedEntity,
  clearDraft,
  isCommittalAnnotation,
  loadDraft,
  numberInText,
  saveDraft,
} from "./annotation-helpers";

const DIRECTION_LABELS: Record<string, string> = {
  bullish: "看多",
  bearish: "看空",
  neutral: "中性",
  watchlist: "观望",
  risk_warning: "风险警示",
};

const EXCLUDE_LABELS: Record<string, string> = {
  image_placeholder: "图片占位/OCR 缺失",
  insufficient_context: "上下文不足",
  non_investment: "非投研内容",
  duplicate: "重复样本",
  other: "其他",
};

const CONVICTION_LEVELS: { value: number; label: string; hint: string }[] = [
  { value: 0.3, label: "标的存疑", hint: "标的未验证或存疑" },
  { value: 0.45, label: "比例≠价位", hint: "涨幅/比例不是具体价格" },
  { value: 0.6, label: "标的可溯", hint: "标的可溯，无明确价位" },
  { value: 0.8, label: "标的+价位", hint: "标的和价位均在原文可溯" },
];

interface StepDraft {
  action_type: string;
  trigger_condition: string;
  target_price_low: string;
  target_price_high: string;
}

interface AltGoldDraft {
  ticker: string;
  direction: GoldExtraction["direction"] | "";
  conviction: number | null;
}

interface FormDraftState {
  sampleVerdict: EvalSampleVerdict;
  excludeReason: string;
  expectedAbstain: boolean;
  ticker: string;
  direction: string;
  conviction: number | null;
  steps: StepDraft[];
  altGolds?: AltGoldDraft[];
  notes: string;
}

function toDraftSteps(chain?: GoldActionStep[] | null): StepDraft[] {
  return (chain ?? []).map((s) => ({
    action_type: s.action_type,
    trigger_condition: s.trigger_condition ?? "",
    target_price_low: s.target_price_low != null ? String(s.target_price_low) : "",
    target_price_high: s.target_price_high != null ? String(s.target_price_high) : "",
  }));
}

function toAltDrafts(alts?: GoldExtraction[] | null): AltGoldDraft[] {
  return (alts ?? []).map((g) => ({
    ticker: g.ticker,
    direction: g.direction,
    conviction: g.conviction ?? null,
  }));
}

function parseModelDraft(raw?: string | null): GoldExtraction | null {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    if (
      typeof obj === "object" && obj !== null &&
      typeof obj.ticker === "string" && typeof obj.direction === "string"
    ) {
      return obj as GoldExtraction;
    }
    return null;
  } catch {
    return null;
  }
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

function isNumericInput(value: string): boolean {
  return !value.trim() || Number.isFinite(Number(value));
}

export function EvalGoldForm({
  item,
  enums,
  reviewerId,
  submitting,
  onSubmit,
  detectedEntities,
  priceToFill,
  onPriceConsumed,
  tickerToFill,
  onTickerConsumed,
  contextBlocks,
}: {
  item: EvalAnnotationItem;
  enums: AnnotationEnums;
  reviewerId: string;
  submitting: boolean;
  onSubmit: (annotation: EvalGoldAnnotation) => void;
  detectedEntities?: DetectedEntity[];
  priceToFill?: string | null;
  onPriceConsumed?: () => void;
  /** 证据卡实体 chip 点击 → 填入主 ticker */
  tickerToFill?: string | null;
  onTickerConsumed?: () => void;
  /** 已并入证据的上下文块（工作台维护）；参与可溯性校验并随提交落盘 */
  contextBlocks?: ContextBlock[];
}) {
  const existing = item.annotation;
  const draftKey = item.id;

  const savedDraft = React.useMemo(() => {
    if (existing) return null;
    return loadDraft<FormDraftState>("eval_gold", draftKey);
  }, [draftKey, existing]);

  const [sampleVerdict, setSampleVerdict] = React.useState<EvalSampleVerdict>(
    savedDraft?.sampleVerdict ?? existing?.sample_verdict ?? "gold",
  );
  const [excludeReason, setExcludeReason] = React.useState<
    EvalGoldAnnotation["exclude_reason"] | ""
  >((savedDraft?.excludeReason as EvalGoldAnnotation["exclude_reason"]) ?? existing?.exclude_reason ?? "");
  const [expectedAbstain, setExpectedAbstain] = React.useState(
    savedDraft?.expectedAbstain ?? existing?.expected_abstain ?? false,
  );
  const [ticker, setTicker] = React.useState(savedDraft?.ticker ?? existing?.gold?.ticker ?? "");
  const [direction, setDirection] = React.useState<GoldExtraction["direction"] | "">(
    (savedDraft?.direction as GoldExtraction["direction"]) ?? existing?.gold?.direction ?? "",
  );
  const [conviction, setConviction] = React.useState<number | null>(
    savedDraft?.conviction ?? existing?.gold?.conviction ?? null,
  );
  const [steps, setSteps] = React.useState<StepDraft[]>(
    savedDraft?.steps ?? toDraftSteps(existing?.gold?.action_chain),
  );
  const [altGolds, setAltGolds] = React.useState<AltGoldDraft[]>(
    savedDraft?.altGolds ?? toAltDrafts(existing?.alt_golds),
  );
  const [notes, setNotes] = React.useState(savedDraft?.notes ?? existing?.notes ?? "");
  const [localError, setLocalError] = React.useState<string | null>(null);
  const [modelDraftOpen, setModelDraftOpen] = React.useState(false);
  const [gapState, setGapState] = React.useState<"idle" | "sending" | "done">("idle");
  const [gapTicker, setGapTicker] = React.useState("");
  const mountTime = React.useRef(Date.now());

  const modelDraft = React.useMemo(() => parseModelDraft(item.draft), [item.draft]);

  // ── Draft persistence ───────────────────────────────────────────────────
  React.useEffect(() => {
    if (existing) return;
    const draft: FormDraftState = {
      sampleVerdict,
      excludeReason: excludeReason || "",
      expectedAbstain,
      ticker,
      direction,
      conviction,
      steps,
      altGolds,
      notes,
    };
    saveDraft("eval_gold", draftKey, draft);
  }, [sampleVerdict, excludeReason, expectedAbstain, ticker, direction, conviction, steps, altGolds, notes, draftKey, existing]);

  // ── Consume price click from EvidenceCard ───────────────────────────────
  React.useEffect(() => {
    if (!priceToFill) return;
    let consumed = false;
    for (let i = 0; i < steps.length; i++) {
      if (!steps[i].target_price_low.trim()) {
        setSteps((s) => s.map((x, j) => (j === i ? { ...x, target_price_low: priceToFill } : x)));
        consumed = true;
        break;
      }
      if (!steps[i].target_price_high.trim()) {
        setSteps((s) => s.map((x, j) => (j === i ? { ...x, target_price_high: priceToFill } : x)));
        consumed = true;
        break;
      }
    }
    if (!consumed && steps.length === 0) {
      setSteps([{
        action_type: enums.action_types[0] ?? "watch",
        trigger_condition: "",
        target_price_low: priceToFill,
        target_price_high: "",
      }]);
    }
    onPriceConsumed?.();
  }, [priceToFill, steps, onPriceConsumed, enums.action_types]);

  // ── Consume ticker click from EvidenceCard entity chips ─────────────────
  React.useEffect(() => {
    if (!tickerToFill) return;
    setSampleVerdict("gold");
    setTicker(tickerToFill);
    setGapState("idle");
    onTickerConsumed?.();
  }, [tickerToFill, onTickerConsumed]);

  // ── 可溯性文本 = 并入的上文 + 证据 + 并入的下文 ─────────────────────────
  const traceText = React.useMemo(() => {
    const ctx = contextBlocks ?? [];
    const before = ctx.filter((b) => b.offset < 0).sort((a, b) => a.offset - b.offset).map((b) => b.content);
    const after = ctx.filter((b) => b.offset > 0).sort((a, b) => a.offset - b.offset).map((b) => b.content);
    return [...before, item.evidence_text, ...after].join("\n");
  }, [contextBlocks, item.evidence_text]);

  // ── Price traceability warnings ─────────────────────────────────────────
  const priceWarnings = React.useMemo(() => {
    const warnings: string[] = [];
    for (let i = 0; i < steps.length; i++) {
      const lo = steps[i].target_price_low.trim();
      const hi = steps[i].target_price_high.trim();
      if (lo && !numberInText(traceText, lo)) warnings.push(`步骤${i + 1} 低价 ${lo} 原文未出现`);
      if (hi && !numberInText(traceText, hi)) warnings.push(`步骤${i + 1} 高价 ${hi} 原文未出现`);
    }
    return warnings;
  }, [steps, traceText]);

  // ── Abstain contradiction check ─────────────────────────────────────────
  const abstainWarning = React.useMemo(() => {
    if (sampleVerdict === "exclude") return null;
    const typed = steps.filter((s) => s.action_type).map((s) => ({ action_type: s.action_type }));
    const committal = isCommittalAnnotation(direction, typed);
    if (expectedAbstain && committal)
      return "矛盾：标记了「应弃权」但方向/链条含承诺动作。弃权项通常用 watchlist + watch。";
    if (!expectedAbstain && !committal && direction && (direction === "neutral" || direction === "watchlist"))
      return "提示：方向为中性/观望且无承诺动作——是否应标记为「应弃权」？按 A 标记。";
    return null;
  }, [sampleVerdict, expectedAbstain, direction, steps]);

  // ── Suggested conviction based on traceability ──────────────────────────
  const suggestedConviction = React.useMemo((): number | null => {
    if (sampleVerdict === "exclude" || expectedAbstain) return null;
    const tickerUpper = ticker.trim().toUpperCase();
    const tickerKnown = detectedEntities?.some((e) => e.ticker === tickerUpper) || traceText.includes(ticker.trim());
    const hasTraceablePrice = steps.some(
      (s) =>
        (s.target_price_low.trim() && numberInText(traceText, s.target_price_low.trim())) ||
        (s.target_price_high.trim() && numberInText(traceText, s.target_price_high.trim())),
    );
    if (!tickerKnown && !ticker.trim()) return null;
    if (hasTraceablePrice && tickerKnown) return 0.8;
    if (tickerKnown) return 0.6;
    const hasUntraceable = steps.some(
      (s) =>
        (s.target_price_low.trim() && !numberInText(traceText, s.target_price_low.trim())) ||
        (s.target_price_high.trim() && !numberInText(traceText, s.target_price_high.trim())),
    );
    if (hasUntraceable) return 0.45;
    return 0.3;
  }, [sampleVerdict, expectedAbstain, ticker, steps, traceText, detectedEntities]);

  // ── Ticker warning (not in registry and not in evidence) ────────────────
  const tickerWarning = React.useMemo(() => {
    const t = ticker.trim();
    if (!t || t === "NONE") return null;
    const inRegistry = detectedEntities?.some((e) => e.ticker === t.toUpperCase());
    const inText = traceText.includes(t);
    if (!inRegistry && !inText) return `"${t}" 不在实体库且原文未出现——请确认 ticker`;
    return null;
  }, [ticker, detectedEntities, traceText]);

  // ── Alt golds warnings ──────────────────────────────────────────────────
  const altWarning = React.useMemo(() => {
    const primary = ticker.trim().toUpperCase();
    const seen = new Set<string>();
    for (const alt of altGolds) {
      const t = alt.ticker.trim().toUpperCase();
      if (!t) continue;
      if (t === primary) return `次要标的 ${t} 与主标的重复`;
      if (seen.has(t)) return `次要标的 ${t} 重复`;
      seen.add(t);
    }
    return null;
  }, [altGolds, ticker]);

  const altRowsComplete = altGolds.every(
    (a) => !a.ticker.trim() || a.direction !== "",
  );

  const priceInputsValid = steps.every(
    (s) => isNumericInput(s.target_price_low) && isNumericInput(s.target_price_high),
  );

  const canSubmit =
    reviewerId.trim().length > 0 &&
    !submitting &&
    (sampleVerdict === "exclude"
      ? Boolean(excludeReason)
      : ticker.trim().length > 0 && direction !== "" && priceInputsValid &&
        !altWarning && altRowsComplete);

  const markAbstain = React.useCallback(() => {
    setSampleVerdict("gold");
    setExpectedAbstain(true);
    setTicker((t) => (t.trim() ? t : "NONE"));
    setDirection((d) => (d ? d : "watchlist"));
    setSteps((s) =>
      s.length ? s : [{ action_type: "watch", trigger_condition: "", target_price_low: "", target_price_high: "" }],
    );
  }, []);

  // ── Adopt model draft ───────────────────────────────────────────────────
  const adoptModelDraft = React.useCallback(() => {
    if (!modelDraft) return;
    setSampleVerdict("gold");
    setTicker(modelDraft.ticker === "NONE" ? "NONE" : modelDraft.ticker);
    setDirection(modelDraft.direction);
    setSteps(toDraftSteps(modelDraft.action_chain));
    if (modelDraft.conviction != null) setConviction(modelDraft.conviction);
    if (modelDraft.direction === "watchlist" && modelDraft.ticker === "NONE") {
      setExpectedAbstain(true);
    }
  }, [modelDraft]);

  // ── Registry gap inline submit ──────────────────────────────────────────
  const submitRegistryGap = React.useCallback(async () => {
    const alias = ticker.trim();
    if (!alias || gapState === "sending") return;
    setGapState("sending");
    try {
      const res = await fetch("/api/annotation/registry-gap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alias,
          suggested_ticker: gapTicker.trim(),
          market: "",
          item_id: item.id,
          reviewer_id: reviewerId.trim(),
        }),
      });
      const body = await res.json();
      setGapState(body.ok ? "done" : "idle");
    } catch {
      setGapState("idle");
    }
  }, [ticker, gapTicker, gapState, item.id, reviewerId]);

  const handleSubmit = React.useCallback(() => {
    if (!canSubmit) return;
    setLocalError(null);
    const duration_ms = Date.now() - mountTime.current;
    const context_blocks = (contextBlocks ?? []).map((b) => ({
      offset: b.offset,
      timestamp: b.timestamp ?? null,
      content: b.content,
    }));

    if (sampleVerdict === "exclude") {
      clearDraft("eval_gold", draftKey);
      onSubmit({
        id: item.id,
        reviewer_id: reviewerId.trim(),
        annotation_schema_version: enums.annotation_schema_version,
        sample_verdict: "exclude",
        exclude_reason: excludeReason || null,
        expected_abstain: false,
        gold: null,
        alt_golds: [],
        context_blocks,
        notes: notes.trim() || null,
        duration_ms,
      });
      return;
    }

    const action_chain: GoldActionStep[] = steps
      .filter((s) => s.action_type)
      .map((s) => ({
        action_type: s.action_type,
        trigger_condition: s.trigger_condition.trim() || null,
        target_price_low: s.target_price_low.trim() ? Number(s.target_price_low) : null,
        target_price_high: s.target_price_high.trim() ? Number(s.target_price_high) : null,
      }));

    if (!priceInputsValid) {
      setLocalError("价格字段必须为空或数字");
      return;
    }

    const alt_golds: GoldExtraction[] = altGolds
      .filter((a) => a.ticker.trim() && a.direction !== "")
      .map((a) => ({
        ticker: a.ticker.trim().toUpperCase(),
        direction: a.direction as GoldExtraction["direction"],
        action_chain: [],
        conviction: a.conviction,
      }));

    clearDraft("eval_gold", draftKey);
    onSubmit({
      id: item.id,
      reviewer_id: reviewerId.trim(),
      annotation_schema_version: enums.annotation_schema_version,
      sample_verdict: "gold",
      exclude_reason: null,
      expected_abstain: expectedAbstain,
      gold: {
        ticker: ticker.trim().toUpperCase(),
        direction: direction as GoldExtraction["direction"],
        action_chain,
        conviction,
      },
      alt_golds,
      context_blocks,
      notes: notes.trim() || null,
      duration_ms,
    });
  }, [
    canSubmit, conviction, direction, draftKey, enums.annotation_schema_version,
    excludeReason, expectedAbstain, item.id, notes, onSubmit, altGolds, contextBlocks,
    priceInputsValid, reviewerId, sampleVerdict, steps, ticker,
  ]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e) || e.metaKey || e.ctrlKey) return;
      if (e.key.toLowerCase() === "a") { e.preventDefault(); markAbstain(); }
      if (e.key.toLowerCase() === "x") { e.preventDefault(); setSampleVerdict("exclude"); }
      const number = Number(e.key);
      if (number >= 1 && number <= enums.directions.length) {
        setSampleVerdict("gold");
        setDirection(enums.directions[number - 1]);
      }
      if (e.key === "Enter") { e.preventDefault(); handleSubmit(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enums.directions, handleSubmit, markAbstain]);

  return (
    <div className="space-y-4">
      {/* ── Verdict selector ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <button
          onClick={() => { setSampleVerdict("gold"); setExpectedAbstain(false); }}
          className={cn(
            "rounded-md border px-3 py-3 text-left text-sm transition-colors",
            sampleVerdict === "gold" && !expectedAbstain
              ? "border-stone-800 bg-stone-900 text-white"
              : "border-stone-200 bg-white hover:bg-stone-50",
          )}
        >
          <CheckCircle2 className="mb-2 h-4 w-4" />
          标 gold
          <div className="mt-1 text-[11px] opacity-60">证据足够，标注结构化答案</div>
        </button>
        <button
          onClick={markAbstain}
          className={cn(
            "rounded-md border px-3 py-3 text-left text-sm transition-colors",
            sampleVerdict === "gold" && expectedAbstain
              ? "border-amber-500 bg-amber-500 text-white"
              : "border-stone-200 bg-white hover:bg-amber-50",
          )}
        >
          <Ban className="mb-2 h-4 w-4" />
          应弃权 <kbd className="ml-1 text-[9px] opacity-60">A</kbd>
          <div className="mt-1 text-[11px] opacity-60">保留样本，但 gold 为 NONE/watchlist</div>
        </button>
        <button
          onClick={() => setSampleVerdict("exclude")}
          className={cn(
            "rounded-md border px-3 py-3 text-left text-sm transition-colors",
            sampleVerdict === "exclude"
              ? "border-red-600 bg-red-600 text-white"
              : "border-stone-200 bg-white hover:bg-red-50",
          )}
        >
          <Trash2 className="mb-2 h-4 w-4" />
          样本无效 <kbd className="ml-1 text-[9px] opacity-60">X</kbd>
          <div className="mt-1 text-[11px] opacity-60">不进入 eval_set.jsonl</div>
        </button>
      </div>

      {/* ── Model draft (collapsed by default to avoid anchoring) ─────── */}
      {modelDraft && sampleVerdict === "gold" && item.status === "pending" && (
        <div className="rounded-lg border border-violet-200 bg-violet-50/40">
          <button
            onClick={() => setModelDraftOpen((o) => !o)}
            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-violet-700"
          >
            <Sparkles className="h-3.5 w-3.5" />
            模型初稿（先形成自己的判断再看，避免锚定）
            <span className="ml-auto text-[10px] opacity-60">{modelDraftOpen ? "收起" : "查看"}</span>
          </button>
          {modelDraftOpen && (
            <div className="border-t border-violet-100 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-white px-2 py-0.5 font-mono">{modelDraft.ticker}</span>
                <span className="rounded bg-white px-2 py-0.5">{DIRECTION_LABELS[modelDraft.direction] ?? modelDraft.direction}</span>
                <span className="text-[10px] text-violet-600/70">
                  {modelDraft.action_chain?.length ?? 0} 步动作链
                </span>
                <button
                  onClick={adoptModelDraft}
                  className="ml-auto rounded border border-violet-300 bg-white px-2.5 py-1 text-[11px] font-medium text-violet-700 hover:bg-violet-100"
                >
                  采纳并修正
                </button>
              </div>
              <pre className="mt-2 max-h-32 overflow-auto rounded bg-white/70 p-2 font-mono text-[10px] leading-relaxed text-foreground/70">
                {JSON.stringify(modelDraft, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* ── Abstain contradiction warning ─────────────────────────────── */}
      {abstainWarning && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {abstainWarning}
        </div>
      )}

      {sampleVerdict === "exclude" ? (
        <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
          <label className="text-[10px] font-medium uppercase tracking-wider text-red-700">排除原因</label>
          <div className="mt-2 flex flex-wrap gap-2">
            {enums.eval_exclude_reasons.map((reason) => (
              <button
                key={reason}
                onClick={() => setExcludeReason(reason)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs",
                  excludeReason === reason
                    ? "border-red-700 bg-red-700 text-white"
                    : "border-red-200 bg-white text-red-700",
                )}
              >
                {EXCLUDE_LABELS[reason] ?? reason}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* ── Ticker + Direction ─────────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-stone-200 bg-white p-4">
              <label className="text-[10px] font-medium uppercase tracking-wider text-foreground/50">
                Gold Ticker
              </label>
              {detectedEntities && detectedEntities.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {detectedEntities.map((e) => (
                    <button
                      key={e.ticker}
                      type="button"
                      onClick={() => setTicker(e.ticker)}
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors",
                        ticker.trim().toUpperCase() === e.ticker
                          ? "border-blue-600 bg-blue-600 text-white"
                          : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100",
                      )}
                    >
                      {e.alias} → {e.ticker}
                    </button>
                  ))}
                </div>
              )}
              <input
                value={ticker}
                onChange={(e) => { setTicker(e.target.value); setGapState("idle"); }}
                placeholder="如 0700.HK / CSIQ / NONE"
                className={cn(
                  "mt-2 w-full rounded-md border px-3 py-2 font-mono text-sm focus:border-stone-400 focus:outline-none",
                  tickerWarning ? "border-amber-400 bg-amber-50/30" : "border-stone-200",
                )}
              />
              {tickerWarning && (
                <div className="mt-1.5 rounded-md border border-amber-200 bg-amber-50/60 px-2 py-1.5">
                  <div className="text-[10px] text-amber-700">{tickerWarning}</div>
                  {gapState === "done" ? (
                    <div className="mt-1 text-[10px] font-medium text-green-700">
                      ✓ 已提交实体库候补（registry_gaps.jsonl）
                    </div>
                  ) : (
                    <div className="mt-1 flex items-center gap-1.5">
                      <input
                        value={gapTicker}
                        onChange={(e) => setGapTicker(e.target.value)}
                        placeholder="建议 ticker（可空）"
                        className="w-32 rounded border border-amber-200 bg-white px-1.5 py-0.5 font-mono text-[10px] focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={submitRegistryGap}
                        disabled={gapState === "sending"}
                        className="rounded border border-amber-300 bg-white px-2 py-0.5 text-[10px] font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                      >
                        {gapState === "sending" ? "提交中…" : "提交实体库候补"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="rounded-lg border border-stone-200 bg-white p-4">
              <label className="text-[10px] font-medium uppercase tracking-wider text-foreground/50">
                Gold 方向
              </label>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {enums.directions.map((value, i) => (
                  <button
                    key={value}
                    onClick={() => setDirection(value)}
                    className={cn(
                      "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                      direction === value
                        ? "border-stone-800 bg-stone-800 text-white"
                        : "border-stone-200 bg-white text-foreground/70 hover:bg-stone-50",
                    )}
                  >
                    <kbd className="mr-1 opacity-50">{i + 1}</kbd>
                    {DIRECTION_LABELS[value] ?? value}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Alt golds（多标的段落） ─────────────────────────────────── */}
          <div className="rounded-lg border border-stone-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-medium uppercase tracking-wider text-foreground/50">
                次要标的（多标的段落）
              </label>
              <button
                onClick={() => setAltGolds((a) => [...a, { ticker: "", direction: "", conviction: null }])}
                className="flex items-center gap-1 rounded-md border border-stone-200 px-2 py-1 text-[11px] text-foreground/60 hover:bg-stone-50"
              >
                <Plus className="h-3 w-3" /> 次要标的
              </button>
            </div>
            {altGolds.length === 0 ? (
              <div className="mt-2 text-[11px] text-foreground/40">
                一段话同时讲多个标的时，主标的之外的填这里——评测 match-any 计分。
                {(detectedEntities?.length ?? 0) >= 2 && (
                  <span className="ml-1 font-medium text-blue-600">检测到本段含多个实体。</span>
                )}
              </div>
            ) : (
              <div className="mt-2 space-y-2">
                {altGolds.map((alt, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <input
                      value={alt.ticker}
                      onChange={(e) => setAltGolds((a) => a.map((x, j) => (j === i ? { ...x, ticker: e.target.value } : x)))}
                      placeholder="ticker"
                      className="w-28 rounded-md border border-stone-200 px-2 py-1.5 font-mono text-xs focus:outline-none"
                    />
                    <select
                      value={alt.direction}
                      onChange={(e) => setAltGolds((a) => a.map((x, j) => (j === i ? { ...x, direction: e.target.value as AltGoldDraft["direction"] } : x)))}
                      className="rounded-md border border-stone-200 px-2 py-1.5 text-xs focus:outline-none"
                    >
                      <option value="">方向…</option>
                      {enums.directions.map((d) => (
                        <option key={d} value={d}>{DIRECTION_LABELS[d] ?? d}</option>
                      ))}
                    </select>
                    <select
                      value={alt.conviction ?? ""}
                      onChange={(e) => setAltGolds((a) => a.map((x, j) => (j === i ? { ...x, conviction: e.target.value ? Number(e.target.value) : null } : x)))}
                      className="rounded-md border border-stone-200 px-2 py-1.5 text-xs focus:outline-none"
                    >
                      <option value="">conviction…</option>
                      {CONVICTION_LEVELS.map((c) => (
                        <option key={c.value} value={c.value}>{c.value} {c.label}</option>
                      ))}
                    </select>
                    {detectedEntities?.filter((e) => e.ticker !== ticker.trim().toUpperCase()).map((e) => (
                      <button
                        key={e.ticker}
                        type="button"
                        onClick={() => setAltGolds((a) => a.map((x, j) => (j === i ? { ...x, ticker: e.ticker } : x)))}
                        className="rounded-full border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[9px] text-blue-700 hover:bg-blue-100"
                      >
                        {e.ticker}
                      </button>
                    ))}
                    <button
                      onClick={() => setAltGolds((a) => a.filter((_, j) => j !== i))}
                      className="ml-auto p-1.5 text-foreground/30 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            {altWarning && (
              <div className="mt-1.5 text-[10px] text-red-600">{altWarning}</div>
            )}
            {!altRowsComplete && (
              <div className="mt-1.5 text-[10px] text-amber-700">次要标的填了 ticker 还需选方向</div>
            )}
          </div>

          {/* ── Conviction ─────────────────────────────────────────────── */}
          <div className="rounded-lg border border-stone-200 bg-white p-4">
            <label className="text-[10px] font-medium uppercase tracking-wider text-foreground/50">
              Conviction 证据强度
            </label>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {CONVICTION_LEVELS.map((cv) => (
                <button
                  key={cv.value}
                  onClick={() => setConviction((cur) => (cur === cv.value ? null : cv.value))}
                  className={cn(
                    "group relative rounded-md border px-3 py-1.5 font-mono text-xs transition-colors",
                    conviction === cv.value
                      ? "border-stone-800 bg-stone-800 text-white"
                      : "border-stone-200 text-foreground/70 hover:bg-stone-50",
                    suggestedConviction === cv.value && conviction !== cv.value &&
                      "ring-2 ring-blue-300 ring-offset-1",
                  )}
                  title={cv.hint}
                >
                  {cv.value}
                  <span className={cn(
                    "ml-1.5 text-[9px]",
                    conviction === cv.value ? "opacity-70" : "opacity-40",
                  )}>
                    {cv.label}
                  </span>
                </button>
              ))}
            </div>
            {suggestedConviction && conviction !== suggestedConviction && (
              <div className="mt-1.5 text-[10px] text-blue-600">
                建议 {suggestedConviction}（{CONVICTION_LEVELS.find((c) => c.value === suggestedConviction)?.hint}）
              </div>
            )}
          </div>

          {/* ── Action Chain ───────────────────────────────────────────── */}
          <div className="rounded-lg border border-stone-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-medium uppercase tracking-wider text-foreground/50">
                Gold Action Chain
              </label>
              <button
                onClick={() =>
                  setSteps((s) => [
                    ...s,
                    { action_type: enums.action_types[0] ?? "watch", trigger_condition: "", target_price_low: "", target_price_high: "" },
                  ])
                }
                className="flex items-center gap-1 rounded-md border border-stone-200 px-2 py-1 text-[11px] text-foreground/60 hover:bg-stone-50"
              >
                <Plus className="h-3 w-3" /> 加步骤
              </button>
            </div>
            {steps.length === 0 && (
              <div className="mt-2 text-[11px] text-foreground/40">
                空链合法（纯方向观点 / 弃权项可不填）。点击原文中的数字可自动创建步骤并填入价位。
              </div>
            )}
            <div className="mt-2 space-y-2">
              {steps.map((step, i) => {
                const loOk = !step.target_price_low.trim() || numberInText(traceText, step.target_price_low.trim());
                const hiOk = !step.target_price_high.trim() || numberInText(traceText, step.target_price_high.trim());
                return (
                  <div key={i}>
                    <div className="flex items-center gap-2">
                      <select
                        value={step.action_type}
                        onChange={(e) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, action_type: e.target.value } : x)))}
                        className="rounded-md border border-stone-200 px-2 py-1.5 text-xs focus:outline-none"
                      >
                        {enums.action_types.map((type) => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                      <input
                        value={step.trigger_condition}
                        onChange={(e) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, trigger_condition: e.target.value } : x)))}
                        placeholder="触发条件"
                        className="min-w-0 flex-1 rounded-md border border-stone-200 px-2 py-1.5 text-xs focus:outline-none"
                      />
                      <input
                        value={step.target_price_low}
                        onChange={(e) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, target_price_low: e.target.value } : x)))}
                        placeholder="低"
                        inputMode="decimal"
                        className={cn(
                          "w-16 rounded-md border px-2 py-1.5 text-xs focus:outline-none",
                          !isNumericInput(step.target_price_low) ? "border-red-400" : !loOk ? "border-amber-400 bg-amber-50/30" : "border-stone-200",
                        )}
                      />
                      <input
                        value={step.target_price_high}
                        onChange={(e) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, target_price_high: e.target.value } : x)))}
                        placeholder="高"
                        inputMode="decimal"
                        className={cn(
                          "w-16 rounded-md border px-2 py-1.5 text-xs focus:outline-none",
                          !isNumericInput(step.target_price_high) ? "border-red-400" : !hiOk ? "border-amber-400 bg-amber-50/30" : "border-stone-200",
                        )}
                      />
                      <button
                        onClick={() => setSteps((s) => s.filter((_, j) => j !== i))}
                        className="p-1.5 text-foreground/30 hover:text-red-600"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {(!loOk || !hiOk) && (
                      <div className="ml-[4.5rem] mt-0.5 text-[10px] text-amber-700">
                        {!loOk && `低价 ${step.target_price_low.trim()} 原文未出现`}
                        {!loOk && !hiOk && "；"}
                        {!hiOk && `高价 ${step.target_price_high.trim()} 原文未出现`}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Price traceability summary ──────────────────────────────── */}
          {priceWarnings.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>价位可溯性警告：{priceWarnings.join("；")}（已并入的上下文计入原文）</div>
            </div>
          )}
        </>
      )}

      {localError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {localError}
        </div>
      )}

      {/* ── Submit ───────────────────────────────────────────────────── */}
      <div className="flex items-start gap-3">
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
            "shrink-0 rounded-md px-5 py-2 text-sm font-medium transition-colors",
            canSubmit
              ? "bg-stone-800 text-white hover:bg-stone-700"
              : "cursor-not-allowed bg-stone-100 text-foreground/30",
          )}
        >
          {submitting ? "提交中..." : item.status !== "pending" ? "更新标注" : "保存并下一条"}
          <kbd className="ml-2 rounded bg-white/20 px-1 text-[9px]">Enter</kbd>
        </button>
      </div>
    </div>
  );
}
