/** Shared utilities for the annotation workbench. */

// ── Entity detection ──────────────────────────────────────────────────────────

export interface DetectedEntity {
  alias: string;
  ticker: string;
  market: string;
}

export function detectEntities(
  text: string,
  aliases: Record<string, { ticker: string; market: string }>,
): DetectedEntity[] {
  const seen = new Set<string>();
  const results: DetectedEntity[] = [];
  const sorted = Object.entries(aliases).sort((a, b) => b[0].length - a[0].length);
  for (const [alias, info] of sorted) {
    if (text.includes(alias) && !seen.has(info.ticker)) {
      seen.add(info.ticker);
      results.push({ alias, ticker: info.ticker, market: info.market });
    }
  }
  return results;
}

// ── Number traceability ───────────────────────────────────────────────────────

export function numberInText(text: string, numStr: string): boolean {
  if (!numStr.trim()) return true;
  const escaped = numStr.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(?<!\\d)${escaped}(?!\\d)`);
  return re.test(text);
}

// ── JSON diff for pair review ─────────────────────────────────────────────────

export interface DiffEntry {
  key: string;
  type: "same" | "changed" | "added" | "removed";
  left?: unknown;
  right?: unknown;
}

export function diffObjects(
  left: Record<string, unknown>,
  right: Record<string, unknown>,
): DiffEntry[] {
  const allKeys = [...new Set([...Object.keys(left), ...Object.keys(right)])];
  return allKeys.map((key) => {
    const l = left[key];
    const r = right[key];
    if (!(key in left)) return { key, type: "added" as const, right: r };
    if (!(key in right)) return { key, type: "removed" as const, left: l };
    if (JSON.stringify(l) === JSON.stringify(r))
      return { key, type: "same" as const, left: l, right: r };
    return { key, type: "changed" as const, left: l, right: r };
  });
}

// ── Abstain contradiction check ───────────────────────────────────────────────

const COMMITTAL_DIRECTIONS = new Set(["bullish", "bearish"]);
const NON_COMMITTAL_ACTIONS = new Set(["watch", "hold"]);

export function isCommittalAnnotation(
  direction: string,
  actionChain: { action_type: string }[],
): boolean {
  if (COMMITTAL_DIRECTIONS.has(direction)) return true;
  return actionChain.some((step) => !NON_COMMITTAL_ACTIONS.has(step.action_type));
}

// ── Draft persistence (sessionStorage) ────────────────────────────────────────

const DRAFT_PREFIX = "finer.annotation.draft";

export function saveDraft(taskId: string, itemId: string, data: unknown): void {
  try {
    sessionStorage.setItem(
      `${DRAFT_PREFIX}.${taskId}.${itemId}`,
      JSON.stringify(data),
    );
  } catch {
    /* quota exceeded */
  }
}

export function loadDraft<T>(taskId: string, itemId: string): T | null {
  try {
    const raw = sessionStorage.getItem(`${DRAFT_PREFIX}.${taskId}.${itemId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearDraft(taskId: string, itemId: string): void {
  try {
    sessionStorage.removeItem(`${DRAFT_PREFIX}.${taskId}.${itemId}`);
  } catch {
    /* ignore */
  }
}
