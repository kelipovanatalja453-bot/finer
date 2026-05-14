"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Minus } from "lucide-react";

type ChannelBackendStatus = "available" | "degraded" | "pending";

interface ChannelInfo {
  id: string;
  emoji: string;
  name: string;
  description: string;
  backendStatus: ChannelBackendStatus;
}

const CHANNELS: ChannelInfo[] = [
  {
    id: "feishu",
    emoji: "\u{1F4CD}",
    name: "飞书",
    description: "从飞书群聊和文档导入投研内容",
    backendStatus: "pending",
  },
  {
    id: "wechat",
    emoji: "\u{1F4AC}",
    name: "微信公众号",
    description: "同步微信公众号文章和推送",
    backendStatus: "available",
  },
  {
    id: "bilibili",
    emoji: "\u{1F3A5}",
    name: "B站",
    description: "下载B站视频并转录为文本",
    backendStatus: "available",
  },
  {
    id: "notebooklm",
    emoji: "\u{1F4D3}",
    name: "NotebookLM",
    description: "从 Google NotebookLM 导入研究笔记",
    backendStatus: "pending",
  },
  {
    id: "local",
    emoji: "\u{1F4C2}",
    name: "本地文件",
    description: "从本地目录导入原始文件",
    backendStatus: "available",
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
};

export function SourceChannelStatus() {
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-6">
      <h3 className="font-bold text-foreground mb-4">数据源渠道</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CHANNELS.map((channel) => {
          const statusCfg = STATUS_CONFIG[channel.backendStatus];
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
                  <StatusIcon className="w-2.5 h-2.5" />
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
