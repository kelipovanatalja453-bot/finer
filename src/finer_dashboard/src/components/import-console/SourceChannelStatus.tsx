"use client";

import React, { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Minus, HelpCircle, Loader2 } from "lucide-react";
import { apiGet, ApiError } from "@/lib/api-client";

/**
 * Channel availability as derived from real backend probes.
 * - available : backend probe says the channel is usable
 * - degraded  : backend reachable but the channel's own service is down
 * - pending   : backend reachable, channel not yet wired (no probe / not implemented)
 * - unknown   : backend unreachable, real state can't be determined (do NOT claim "available")
 * - checking  : probe in flight
 */
type ChannelBackendStatus =
  | "available"
  | "degraded"
  | "pending"
  | "unknown"
  | "checking";

interface ChannelMeta {
  id: string;
  emoji: string;
  name: string;
  description: string;
}

const CHANNELS: ChannelMeta[] = [
  {
    id: "feishu",
    emoji: "\u{1F4CD}",
    name: "飞书",
    description: "从飞书群聊和文档导入投研内容",
  },
  {
    id: "wechat",
    emoji: "\u{1F4AC}",
    name: "微信公众号",
    description: "同步微信公众号文章和推送",
  },
  {
    id: "bilibili",
    emoji: "\u{1F3A5}",
    name: "B站",
    description: "下载B站视频并转录为文本",
  },
  {
    id: "notebooklm",
    emoji: "\u{1F4D3}",
    name: "NotebookLM",
    description: "从 Google NotebookLM 导入研究笔记",
  },
  {
    id: "local",
    emoji: "\u{1F4C2}",
    name: "本地文件",
    description: "从本地目录导入原始文件",
  },
];

const STATUS_CONFIG: Record<
  ChannelBackendStatus,
  { label: string; color: string; bgColor: string; icon: React.ElementType }
> = {
  available: {
    label: "可用",
    color: "text-green-700",
    bgColor: "bg-green-50 border-green-200",
    icon: CheckCircle,
  },
  degraded: {
    label: "降级",
    color: "text-yellow-700",
    bgColor: "bg-yellow-50 border-yellow-200",
    icon: AlertCircle,
  },
  pending: {
    label: "待接入",
    color: "text-stone-500",
    bgColor: "bg-stone-50 border-stone-200",
    icon: Minus,
  },
  unknown: {
    label: "未知",
    color: "text-stone-500",
    bgColor: "bg-stone-50 border-stone-200",
    icon: HelpCircle,
  },
  checking: {
    label: "检测中",
    color: "text-blue-600",
    bgColor: "bg-blue-50 border-blue-200",
    icon: Loader2,
  },
};

interface ExporterHealth {
  available: boolean;
  url: string;
  latency_ms?: number | null;
  error?: string | null;
}

/**
 * Probe real backend endpoints and derive per-channel status.
 *
 * Only two cheap, unauthenticated probes exist today:
 *  - GET /api/wechat/exporter/health  → drives the wechat channel directly.
 *  - GET /api/sources/status          → generic "backend reachable" signal.
 *
 * feishu / bilibili / local have no dedicated per-channel probe; they are
 * reachable-if-backend-up integrations, so backend reachability stands in for
 * their availability. notebooklm needs Google auth and has no cheap probe, so
 * it stays "pending" while the backend is up. When the backend itself is
 * unreachable, every channel degrades to "unknown" rather than a false "可用".
 */
function deriveStatuses(
  backendReachable: boolean,
  wechatHealth: ExporterHealth | null,
): Record<string, ChannelBackendStatus> {
  if (!backendReachable) {
    return Object.fromEntries(
      CHANNELS.map((c) => [c.id, "unknown" as ChannelBackendStatus]),
    );
  }

  return {
    feishu: "available",
    bilibili: "available",
    local: "available",
    notebooklm: "pending",
    wechat: wechatHealth
      ? wechatHealth.available
        ? "available"
        : "degraded"
      : "unknown",
  };
}

export function SourceChannelStatus() {
  const [statuses, setStatuses] = useState<Record<string, ChannelBackendStatus>>(
    () => Object.fromEntries(CHANNELS.map((c) => [c.id, "checking"])),
  );

  const probe = useCallback(async () => {
    setStatuses(Object.fromEntries(CHANNELS.map((c) => [c.id, "checking"])));

    // Probe wechat exporter and a generic backend-up signal in parallel.
    // A rejection here means the backend (or the proxy to it) is unreachable.
    const [wechatResult, sourcesResult] = await Promise.allSettled([
      apiGet<ExporterHealth>("/api/wechat/exporter/health"),
      apiGet<unknown>("/api/sources/status"),
    ]);

    // Backend is considered reachable if either probe produced a real HTTP
    // response. A network/502/timeout error surfaces as status 0 / 502 here.
    const reachable = [wechatResult, sourcesResult].some((r) => {
      if (r.status === "fulfilled") return true;
      if (r.reason instanceof ApiError) {
        // status 0 = never reached server; 502 = proxy could not connect.
        return r.reason.status !== 0 && r.reason.status !== 502;
      }
      return false;
    });

    const wechatHealth =
      wechatResult.status === "fulfilled" ? wechatResult.value : null;

    setStatuses(deriveStatuses(reachable, wechatHealth));
  }, []);

  useEffect(() => {
    probe();
  }, [probe]);

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-6">
      <h3 className="font-bold text-foreground mb-4">数据源渠道</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CHANNELS.map((channel) => {
          const status = statuses[channel.id] ?? "unknown";
          const statusCfg = STATUS_CONFIG[status];
          const StatusIcon = statusCfg.icon;
          return (
            <div
              key={channel.id}
              className={cn(
                "p-4 rounded-lg border border-stone-200 bg-stone-50/50",
                "hover:border-stone-300 transition-colors"
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{channel.emoji}</span>
                  <span className="font-medium text-sm text-foreground">
                    {channel.name}
                  </span>
                </div>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded-full border",
                    statusCfg.bgColor,
                    statusCfg.color
                  )}
                >
                  <StatusIcon
                    className={cn(
                      "w-2.5 h-2.5",
                      status === "checking" && "animate-spin"
                    )}
                  />
                  {statusCfg.label}
                </span>
              </div>
              <p className="text-xs text-foreground/50 leading-relaxed">
                {channel.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
