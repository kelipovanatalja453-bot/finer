"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  LineChart,
  Plus,
  Play,
  Pause,
  Trash2,
  Loader2,
  Calendar,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Clock,
  XCircle,
} from "lucide-react";
import type { BacktestTask } from "@/lib/contracts";

const mockTasks: BacktestTask[] = [
  {
    id: "bt-1",
    name: "科技 KOL 组合回测",
    kolIds: ["kol-1", "kol-3"],
    kolNames: ["投研老王", "量化小李"],
    status: "completed",
    startDate: "2025-01-01",
    endDate: "2026-04-24",
    createdAt: "2026-04-20",
    completedAt: "2026-04-20",
    config: { initialCapital: 100000, positionSize: 0.1 },
    metrics: {
      totalReturn: 45.2,
      annualizedReturn: 32.5,
      sharpeRatio: 1.85,
      maxDrawdown: -12.3,
      winRate: 68,
      totalTrades: 156,
    },
  },
  {
    id: "bt-2",
    name: "全量 KOL 回测",
    kolIds: ["kol-1", "kol-2", "kol-3", "kol-4"],
    kolNames: ["投研老王", "价值投资张", "量化小李", "趋势王"],
    status: "running",
    startDate: "2025-01-01",
    endDate: "2026-04-24",
    createdAt: "2026-04-23",
    config: { initialCapital: 100000, positionSize: 0.1 },
  },
  {
    id: "bt-3",
    name: "消费赛道回测",
    kolIds: ["kol-2"],
    kolNames: ["价值投资张"],
    status: "pending",
    startDate: "2025-06-01",
    endDate: "2026-04-24",
    createdAt: "2026-04-24",
    config: { initialCapital: 50000, positionSize: 0.15 },
  },
];

function getStatusIcon(status: BacktestTask["status"]) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-4 h-4 text-green-600" />;
    case "running":
      return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />;
    case "pending":
      return <Clock className="w-4 h-4 text-amber-600" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-red-600" />;
  }
}

function getStatusLabel(status: BacktestTask["status"]) {
  const labels = {
    completed: "已完成",
    running: "运行中",
    pending: "等待中",
    failed: "失败",
  };
  return labels[status];
}

function getStatusColor(status: BacktestTask["status"]) {
  const colors = {
    completed: "text-green-600 bg-green-50",
    running: "text-blue-600 bg-blue-50",
    pending: "text-amber-600 bg-amber-50",
    failed: "text-red-600 bg-red-50",
  };
  return colors[status];
}

export default function BacktestManagePage() {
  const [tasks, setTasks] = useState<BacktestTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setTasks(mockTasks);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="container py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">回测管理</h1>
          <p className="text-sm text-foreground/60 mt-1">
            创建和管理回测任务
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-morningstar-red text-white rounded-md hover:bg-morningstar-red/90 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          新建回测
        </button>
      </div>

      {/* Create Form Placeholder */}
      {showCreate && (
        <div className="bg-white border border-stone-200 rounded-lg p-6 mb-8">
          <h2 className="text-lg font-bold mb-4">新建回测任务</h2>
          <div className="h-32 flex items-center justify-center text-foreground/40 border border-dashed border-stone-300 rounded">
            <div className="text-center">
              <Plus className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">回测配置表单（待实现）</p>
            </div>
          </div>
        </div>
      )}

      {/* Task List */}
      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-foreground/30" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-foreground/40">
          <div className="text-center">
            <LineChart className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>暂无回测任务</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="bg-white border border-stone-200 rounded-lg p-4 hover:border-stone-300 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  {/* Header */}
                  <div className="flex items-center gap-3 mb-2">
                    {getStatusIcon(task.status)}
                    <h3 className="font-bold">{task.name}</h3>
                    <span
                      className={cn(
                        "px-2 py-0.5 text-xs font-medium rounded",
                        getStatusColor(task.status)
                      )}
                    >
                      {getStatusLabel(task.status)}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="flex flex-wrap items-center gap-4 text-sm text-foreground/60">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {task.startDate} ~ {task.endDate}
                    </div>
                    <div className="flex items-center gap-1">
                      {task.kolNames.slice(0, 2).join(", ")}
                      {task.kolNames.length > 2 && ` +${task.kolNames.length - 2}`}
                    </div>
                    <div>创建于 {task.createdAt}</div>
                  </div>

                  {/* Metrics */}
                  {task.metrics && (
                    <div className="flex items-center gap-6 mt-3 pt-3 border-t border-stone-100">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-foreground/50">总收益</span>
                        <span
                          className={cn(
                            "text-sm font-bold flex items-center gap-1",
                            task.metrics.totalReturn >= 0
                              ? "text-green-600"
                              : "text-red-600"
                          )}
                        >
                          {task.metrics.totalReturn >= 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {task.metrics.totalReturn.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-foreground/50">夏普</span>
                        <span className="text-sm font-bold">
                          {task.metrics.sharpeRatio.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-foreground/50">最大回撤</span>
                        <span className="text-sm font-bold text-red-600">
                          {task.metrics.maxDrawdown.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 ml-4">
                  {task.status === "pending" && (
                    <button className="p-2 hover:bg-stone-100 rounded transition-colors">
                      <Play className="w-4 h-4 text-green-600" />
                    </button>
                  )}
                  {task.status === "running" && (
                    <button className="p-2 hover:bg-stone-100 rounded transition-colors">
                      <Pause className="w-4 h-4 text-amber-600" />
                    </button>
                  )}
                  <button className="p-2 hover:bg-stone-100 rounded transition-colors">
                    <Trash2 className="w-4 h-4 text-foreground/40" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
