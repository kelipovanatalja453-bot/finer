"use client";

import React from "react";
import { LineChart, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MarketWindowResult } from "@/lib/contracts";
import type { DetectedEntity } from "./annotation-helpers";

function Sparkline({ window }: { window: NonNullable<MarketWindowResult["window"]> }) {
  if (window.length < 2) return null;
  const W = 220;
  const H = 48;
  const closes = window.map((b) => b.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const points = closes
    .map((c, i) => {
      const x = (i / (closes.length - 1)) * W;
      const y = H - ((c - min) / span) * (H - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const last = closes[closes.length - 1];
  const first = closes[0];
  const up = last >= first;
  return (
    <div className="mt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-12 w-full" preserveAspectRatio="none">
        <polyline
          points={points}
          fill="none"
          strokeWidth="1.5"
          className={up ? "stroke-red-500" : "stroke-green-600"}
        />
      </svg>
      <div className="flex justify-between text-[9px] text-foreground/40">
        <span>{window[0].trade_date}</span>
        <span className="font-mono">{min.toFixed(2)} ~ {max.toFixed(2)}</span>
        <span>{window[window.length - 1].trade_date}</span>
      </div>
    </div>
  );
}

export function MarketPanel({
  entities,
  anchorDate,
}: {
  entities: DetectedEntity[];
  /** item.timestamp，取日期部分作锚定日 */
  anchorDate?: string | null;
}) {
  const [active, setActive] = React.useState(0);
  const [result, setResult] = React.useState<MarketWindowResult | null>(null);
  const [loading, setLoading] = React.useState(false);

  const date = (anchorDate ?? "").slice(0, 10);
  const ticker = entities[active]?.ticker;

  React.useEffect(() => {
    setActive(0);
  }, [entities]);

  React.useEffect(() => {
    if (!ticker || !date) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`/api/annotation/market?ticker=${encodeURIComponent(ticker)}&date=${encodeURIComponent(date)}`)
      .then((res) => res.json())
      .then((body) => {
        if (cancelled) return;
        setResult(body.ok ? (body.data as MarketWindowResult) : null);
      })
      .catch(() => { if (!cancelled) setResult(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, date]);

  if (entities.length === 0 || !date) return null;

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex items-center justify-between border-b border-stone-100 px-4 py-2">
        <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-foreground/50">
          <LineChart className="h-3 w-3" />
          行情对照
          <span className="normal-case tracking-normal">锚定 {date}</span>
        </div>
        {loading && <Loader2 className="h-3 w-3 animate-spin text-foreground/30" />}
      </div>

      {entities.length > 1 && (
        <div className="flex flex-wrap gap-1 border-b border-stone-100 px-3 py-1.5">
          {entities.map((e, i) => (
            <button
              key={e.ticker}
              onClick={() => setActive(i)}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] transition-colors",
                i === active
                  ? "bg-stone-800 text-white"
                  : "bg-stone-50 text-foreground/50 hover:bg-stone-100",
              )}
            >
              {e.ticker}
            </button>
          ))}
        </div>
      )}

      <div className="px-4 py-3">
        {!result && !loading && (
          <div className="text-[11px] text-foreground/40">行情查询失败，可稍后重试</div>
        )}
        {result?.coverage === "local" && (
          <>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-semibold">{result.name ?? result.ts_code}</span>
              <span className="font-mono text-lg">{result.anchor_close?.toFixed(2)}</span>
              {result.anchor_pct_chg != null && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-mono text-[11px] font-medium",
                    result.anchor_pct_chg >= 0 ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700",
                  )}
                >
                  {result.anchor_pct_chg >= 0 ? "+" : ""}{result.anchor_pct_chg.toFixed(2)}%
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-foreground/40">{result.anchor_date}</span>
            </div>
            {result.window && <Sparkline window={result.window} />}
            <div className="mt-1 text-[10px] text-foreground/35">
              qfq 前复权收盘 · 验证目标价量级（比例 ≠ 价位）
            </div>
          </>
        )}
        {result && result.coverage !== "local" && (
          <div className="text-[11px] leading-relaxed text-foreground/50">
            {result.coverage === "unsupported_market" && (
              <>本地行情库暂不覆盖 <span className="font-mono">{result.market}</span> 市场（仅 A 股日线）</>
            )}
            {result.coverage === "no_local_data" && (result.hint ?? "本地行情库未同步")}
            {result.coverage === "unknown_ticker" && (result.hint ?? "无法解析该 ticker")}
          </div>
        )}
      </div>
    </div>
  );
}
