"use client";

import React from "react";
import { CheckCircle2, AlertCircle, Loader2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

export type SyncStatusType = "idle" | "syncing" | "success" | "error";

interface SyncStatusProps {
  status: SyncStatusType;
  message?: string;
  progress?: number; // 0-100
  timestamp?: string;
}

export function SyncStatus({ status, message, progress, timestamp }: SyncStatusProps) {
  const statusConfig = {
    idle: {
      icon: Clock,
      color: "text-stone-400",
      bgColor: "bg-stone-50",
      borderColor: "border-stone-200",
      label: "等待同步",
    },
    syncing: {
      icon: Loader2,
      color: "text-blue-500",
      bgColor: "bg-blue-50",
      borderColor: "border-blue-200",
      label: "同步中",
    },
    success: {
      icon: CheckCircle2,
      color: "text-green-600",
      bgColor: "bg-green-50",
      borderColor: "border-green-200",
      label: "同步成功",
    },
    error: {
      icon: AlertCircle,
      color: "text-morningstar-red",
      bgColor: "bg-red-50",
      borderColor: "border-red-200",
      label: "同步失败",
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn("p-4 border rounded-sm", config.bgColor, config.borderColor)}>
      <div className="flex items-center gap-3">
        <Icon
          className={cn(
            "w-5 h-5",
            config.color,
            status === "syncing" && "animate-spin"
          )}
          strokeWidth={2}
        />
        <div className="flex-1">
          <p className={cn("text-sm font-bold", config.color)}>{config.label}</p>
          {message && (
            <p className="text-xs text-foreground/60 mt-0.5">{message}</p>
          )}
        </div>
        {timestamp && (
          <span className="text-[10px] text-foreground/40 tabular-nums">
            {timestamp}
          </span>
        )}
      </div>

      {/* Progress Bar */}
      {status === "syncing" && typeof progress === "number" && (
        <div className="mt-3">
          <div className="h-2 bg-white rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
          <p className="text-[10px] text-foreground/50 mt-1 text-right">
            {progress}%
          </p>
        </div>
      )}
    </div>
  );
}