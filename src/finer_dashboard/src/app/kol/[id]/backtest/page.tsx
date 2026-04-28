"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Loader2,
} from "lucide-react";
import type { BacktestTask } from "@/lib/contracts";

type BacktestResult = BacktestTask & {
  trades: NonNullable<BacktestTask["trades"]>;
};

const mockBacktest: BacktestResult = {
  id: "bt-1",
  name: "投研老王回测",
  kolIds: ["kol-1"],
  kolNames: ["投研老王"],
  status: "completed",
  startDate: "2025-01-01",
  endDate: "2026-04-24",
  createdAt: "2026-04-20",
  completedAt: "2026-04-20",
  config: {
    initialCapital: 100000,
    positionSize: 0.1,
  },
  metrics: {
    totalReturn: 45.2,
    annualizedReturn: 32.5,
    sharpeRatio: 1.85,
    maxDrawdown: -12.3,
    winRate: 68,
    totalTrades: 156,
  },
  trades: [
    {
      id: "t1",
      ticker: "NVDA",
      direction: "long",
      entryDate: "2026-01-15",
      exitDate: "2026-02-20",
      entryPrice: 450,
      exitPrice: 520,
      return: 15.5,
      opinionId: "e1",
    },
    {
      id: "t2",
      ticker: "TSLA",
      direction: "short",
      entryDate: "2026-03-01",
      exitDate: "2026-03-15",
      entryPrice: 280,
      exitPrice: 260,
      return: 7.1,
      opinionId: "e3",
    },
    {
      id: "t3",
      ticker: "AAPL",
      direction: "long",
      entryDate: "2026-02-10",
      exitDate: "2026-03-10",
      entryPrice: 180,
      exitPrice: 175,
      return: -2.8,
      opinionId: "e2",
    },
  ],
};

export default function KOLBacktestPage() {
  const params = useParams();
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setBacktest(mockBacktest);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [params.id]);

  if (loading) {
    return (
      <div className="container py-8 h-[80vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-foreground/30" />
      </div>
    );
  }

  if (!backtest) {
    return (
      <div className="container py-8">
        <div className="text-center text-foreground/60">回测结果不存在</div>
      </div>
    );
  }

  return (
    <div className="container py-8">
      {/* Back link */}
      <Link
        href={`/kol/${params.id}`}
        className="inline-flex items-center gap-2 text-sm text-foreground/60 hover:text-foreground mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        返回 KOL 详情
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">
          {backtest.kolNames.join(", ")} 的回测结果
        </h1>
        <p className="text-sm text-foreground/60 mt-1">
          {backtest.startDate} ~ {backtest.endDate}
        </p>
      </div>

      {/* Config Summary */}
      <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 mb-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-foreground/50">初始资金：</span>
            <span className="font-bold">${backtest.config.initialCapital.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-foreground/50">单笔仓位：</span>
            <span className="font-bold">{(backtest.config.positionSize * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="text-foreground/50">总交易数：</span>
            <span className="font-bold">{backtest.metrics?.totalTrades ?? "-"}</span>
          </div>
          <div>
            <span className="text-foreground/50">胜率：</span>
            <span className="font-bold">{backtest.metrics ? `${backtest.metrics.winRate}%` : "-"}</span>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      {backtest.metrics && (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            总收益
          </div>
          <div
            className={cn(
              "text-2xl font-bold flex items-center gap-2",
              backtest.metrics.totalReturn >= 0 ? "text-green-600" : "text-red-600"
            )}
          >
            {backtest.metrics.totalReturn >= 0 ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )}
            {backtest.metrics.totalReturn.toFixed(1)}%
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            年化收益
          </div>
          <div className="text-2xl font-bold text-green-600">
            {backtest.metrics.annualizedReturn.toFixed(1)}%
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            夏普比率
          </div>
          <div className="text-2xl font-bold">{backtest.metrics.sharpeRatio.toFixed(2)}</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-xs text-foreground/50 uppercase tracking-wider mb-2">
            最大回撤
          </div>
          <div className="text-2xl font-bold text-red-600">
            {backtest.metrics.maxDrawdown.toFixed(1)}%
          </div>
        </div>
      </div>
      )}

      {/* Trade History */}
      <div className="mb-6">
        <h2 className="text-lg font-bold mb-4">交易记录</h2>
        <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-foreground/60">标的</th>
                <th className="px-4 py-3 text-left font-medium text-foreground/60">方向</th>
                <th className="px-4 py-3 text-left font-medium text-foreground/60">入场</th>
                <th className="px-4 py-3 text-left font-medium text-foreground/60">出场</th>
                <th className="px-4 py-3 text-right font-medium text-foreground/60">收益</th>
              </tr>
            </thead>
            <tbody>
              {backtest.trades.map((trade) => (
                <tr key={trade.id} className="border-b border-stone-100 last:border-0">
                  <td className="px-4 py-3 font-medium">{trade.ticker}</td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "px-2 py-0.5 text-xs font-medium rounded",
                        trade.direction === "long"
                          ? "text-green-600 bg-green-50"
                          : "text-red-600 bg-red-50"
                      )}
                    >
                      {trade.direction === "long" ? "做多" : "做空"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-foreground/70">
                    ${trade.entryPrice.toFixed(2)}
                    <span className="text-xs text-foreground/50 ml-1">
                      ({trade.entryDate})
                    </span>
                  </td>
                  <td className="px-4 py-3 text-foreground/70">
                    ${trade.exitPrice.toFixed(2)}
                    <span className="text-xs text-foreground/50 ml-1">
                      ({trade.exitDate})
                    </span>
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right font-bold",
                      trade.return >= 0 ? "text-green-600" : "text-red-600"
                    )}
                  >
                    {trade.return >= 0 ? "+" : ""}
                    {trade.return.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Chart Placeholder */}
      <div className="bg-white border border-stone-200 rounded-lg p-8">
        <div className="h-64 flex items-center justify-center text-foreground/40">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>收益曲线</p>
            <p className="text-xs mt-1">（待实现）</p>
          </div>
        </div>
      </div>
    </div>
  );
}
