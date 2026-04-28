"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Settings,
  Database,
  Users,
  MessageCircle,
  Video,
  RefreshCw,
  CheckCircle,
  XCircle,
  ExternalLink,
} from "lucide-react";

type DataSource = {
  id: string;
  name: string;
  type: "feishu" | "wechat" | "bilibili";
  status: "connected" | "disconnected" | "error";
  lastSync?: string;
  config: Record<string, string>;
};

const mockDataSources: DataSource[] = [
  {
    id: "ds-1",
    name: "投研群飞书",
    type: "feishu",
    status: "connected",
    lastSync: "2026-04-24 10:30",
    config: { appId: "cli_xxx", folderToken: "fldcn_xxx" },
  },
  {
    id: "ds-2",
    name: "公众号数据",
    type: "wechat",
    status: "connected",
    lastSync: "2026-04-23 18:00",
    config: { accountId: "gh_xxx" },
  },
  {
    id: "ds-3",
    name: "B站 UP主",
    type: "bilibili",
    status: "disconnected",
    config: { mid: "0" },
  },
];

type KOLConfig = {
  id: string;
  name: string;
  platform: string;
  platformId: string;
  enabled: boolean;
};

const mockKOLConfigs: KOLConfig[] = [
  { id: "kol-1", name: "投研老王", platform: "wechat", platformId: "xxx123", enabled: true },
  { id: "kol-2", name: "价值投资张", platform: "bilibili", platformId: "bili456", enabled: true },
  { id: "kol-3", name: "量化小李", platform: "feishu", platformId: "feishu789", enabled: true },
];

function getTypeIcon(type: DataSource["type"]) {
  switch (type) {
    case "feishu":
      return <Database className="w-5 h-5" />;
    case "wechat":
      return <MessageCircle className="w-5 h-5" />;
    case "bilibili":
      return <Video className="w-5 h-5" />;
  }
}

function getTypeLabel(type: DataSource["type"]) {
  const labels = {
    feishu: "飞书",
    wechat: "微信公众号",
    bilibili: "B站",
  };
  return labels[type];
}

function getStatusIcon(status: DataSource["status"]) {
  switch (status) {
    case "connected":
      return <CheckCircle className="w-4 h-4 text-green-600" />;
    case "disconnected":
      return <XCircle className="w-4 h-4 text-stone-400" />;
    case "error":
      return <XCircle className="w-4 h-4 text-red-600" />;
  }
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"datasources" | "kols" | "system">(
    "datasources"
  );
  const [dataSources] = useState(mockDataSources);
  const [kolConfigs, setKOLConfigs] = useState(mockKOLConfigs);

  return (
    <div className="container py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">系统设置</h1>
        <p className="text-sm text-foreground/60 mt-1">
          配置数据源、管理 KOL 和系统参数
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-stone-200 mb-6">
        {[
          { key: "datasources", label: "数据源配置", icon: Database },
          { key: "kols", label: "KOL 管理", icon: Users },
          { key: "system", label: "系统设置", icon: Settings },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.key
                  ? "border-morningstar-red text-foreground"
                  : "border-transparent text-foreground/60 hover:text-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === "datasources" && (
        <div className="space-y-4">
          {dataSources.map((source) => (
            <div
              key={source.id}
              className="bg-white border border-stone-200 rounded-lg p-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-stone-100 rounded-lg">
                    {getTypeIcon(source.type)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-bold">{source.name}</h3>
                      {getStatusIcon(source.status)}
                    </div>
                    <div className="text-sm text-foreground/60">
                      {getTypeLabel(source.type)}
                      {source.lastSync && ` · 上次同步: ${source.lastSync}`}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-stone-200 rounded hover:bg-stone-50 transition-colors">
                    <RefreshCw className="w-3 h-3" />
                    同步
                  </button>
                  <button className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-stone-200 rounded hover:bg-stone-50 transition-colors">
                    <ExternalLink className="w-3 h-3" />
                    配置
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "kols" && (
        <div>
          <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 border-b border-stone-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-foreground/60">
                    KOL
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-foreground/60">
                    平台
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-foreground/60">
                    平台 ID
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-foreground/60">
                    启用
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-foreground/60">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {kolConfigs.map((kol) => (
                  <tr key={kol.id} className="border-b border-stone-100 last:border-0">
                    <td className="px-4 py-3 font-medium">{kol.name}</td>
                    <td className="px-4 py-3 text-foreground/60">
                      {getTypeLabel(kol.platform as DataSource["type"])}
                    </td>
                    <td className="px-4 py-3 text-foreground/60 font-mono text-xs">
                      {kol.platformId}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() =>
                          setKOLConfigs(
                            kolConfigs.map((k) =>
                              k.id === kol.id ? { ...k, enabled: !k.enabled } : k
                            )
                          )
                        }
                        className={cn(
                          "w-10 h-5 rounded-full transition-colors relative",
                          kol.enabled ? "bg-green-500" : "bg-stone-300"
                        )}
                      >
                        <span
                          className={cn(
                            "absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow",
                            kol.enabled ? "translate-x-5" : "translate-x-0.5"
                          )}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button className="px-2 py-1 text-xs text-foreground/60 hover:text-foreground transition-colors">
                        编辑
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "system" && (
        <div className="bg-white border border-stone-200 rounded-lg p-6">
          <h3 className="font-bold mb-4">系统配置</h3>
          <div className="h-48 flex items-center justify-center text-foreground/40 border border-dashed border-stone-300 rounded">
            <div className="text-center">
              <Settings className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">系统配置表单（待实现）</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
