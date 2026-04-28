/**
 * Mock data for frontend development.
 * Replace with real API calls in production.
 */

import type { KOL, BacktestTask } from "./contracts";

// KOL list mock data
export const mockKOLs: KOL[] = [
  {
    id: "kol-1",
    name: "投研老王",
    platform: "wechat",
    platformId: "xxx123",
    overallScore: 4.2,
    dimensionScores: { accuracy: 4.5, timeliness: 4.0, clarity: 3.8, depth: 4.2, consistency: 4.3 },
    accuracy: 68,
    avgReturn: 12.5,
    totalOpinions: 156,
    lastActive: "2026-04-23",
    tags: ["科技", "半导体"],
    enabled: true,
  },
  {
    id: "kol-2",
    name: "价值投资张",
    platform: "bilibili",
    platformId: "bili456",
    overallScore: 3.8,
    dimensionScores: { accuracy: 3.5, timeliness: 3.8, clarity: 4.0, depth: 3.8, consistency: 3.9 },
    accuracy: 55,
    avgReturn: 8.2,
    totalOpinions: 89,
    lastActive: "2026-04-22",
    tags: ["消费", "医药"],
    enabled: true,
  },
  {
    id: "kol-3",
    name: "量化小李",
    platform: "feishu",
    platformId: "feishu789",
    overallScore: 4.5,
    dimensionScores: { accuracy: 4.8, timeliness: 4.5, clarity: 4.2, depth: 4.6, consistency: 4.4 },
    accuracy: 72,
    avgReturn: 18.3,
    totalOpinions: 234,
    lastActive: "2026-04-24",
    tags: ["量化", "期货"],
    enabled: true,
  },
];

// KOL detail mock data
export const mockKOLDetail: Record<string, {
  timeline: Array<{ id: string; ticker: string; direction: string; timestamp: string; confidence: number }>;
  radar: Record<string, number>;
  returns: { labels: string[]; values: number[] };
}> = {
  "kol-1": {
    timeline: [
      { id: "1", ticker: "NVDA", direction: "bullish", timestamp: "2026-04-20", confidence: 0.85 },
      { id: "2", ticker: "TSLA", direction: "bearish", timestamp: "2026-04-18", confidence: 0.72 },
      { id: "3", ticker: "AAPL", direction: "bullish", timestamp: "2026-04-15", confidence: 0.91 },
    ],
    radar: { accuracy: 4.5, timeliness: 4.0, clarity: 3.8, depth: 4.2, consistency: 4.3 },
    returns: {
      labels: ["Jan", "Feb", "Mar", "Apr"],
      values: [5.2, 8.1, 12.5, 15.3],
    },
  },
  "kol-2": {
    timeline: [
      { id: "1", ticker: "MOUTAI", direction: "bullish", timestamp: "2026-04-19", confidence: 0.78 },
      { id: "2", ticker: "BYD", direction: "neutral", timestamp: "2026-04-17", confidence: 0.65 },
    ],
    radar: { accuracy: 3.5, timeliness: 3.8, clarity: 4.0, depth: 3.8, consistency: 3.9 },
    returns: {
      labels: ["Jan", "Feb", "Mar", "Apr"],
      values: [2.1, 4.5, 6.8, 8.2],
    },
  },
  "kol-3": {
    timeline: [
      { id: "1", ticker: "ES", direction: "bullish", timestamp: "2026-04-22", confidence: 0.92 },
      { id: "2", ticker: "NQ", direction: "bearish", timestamp: "2026-04-21", confidence: 0.88 },
      { id: "3", ticker: "GC", direction: "bullish", timestamp: "2026-04-20", confidence: 0.75 },
    ],
    radar: { accuracy: 4.8, timeliness: 4.5, clarity: 4.2, depth: 4.6, consistency: 4.4 },
    returns: {
      labels: ["Jan", "Feb", "Mar", "Apr"],
      values: [8.5, 12.3, 15.8, 18.3],
    },
  },
};

// Backtest task mock data
export const mockBacktestTasks: BacktestTask[] = [
  {
    id: "task-1",
    name: "投研老王回测",
    kolIds: ["kol-1"],
    kolNames: ["投研老王"],
    status: "completed",
    startDate: "2025-01-01",
    endDate: "2025-12-31",
    createdAt: "2026-04-20",
    config: { initialCapital: 100000, positionSize: 0.1 },
    metrics: { totalReturn: 45.2, winRate: 62, maxDrawdown: 15.3, sharpeRatio: 1.85, annualizedReturn: 45.2, totalTrades: 50 },
  },
  {
    id: "task-2",
    name: "量化小李回测",
    kolIds: ["kol-3"],
    kolNames: ["量化小李"],
    status: "running",
    startDate: "2025-01-01",
    endDate: "2025-12-31",
    createdAt: "2026-04-24",
    config: { initialCapital: 100000, positionSize: 0.1 },
  },
  {
    id: "task-3",
    name: "价值投资张回测",
    kolIds: ["kol-2"],
    kolNames: ["价值投资张"],
    status: "pending",
    startDate: "2025-06-01",
    endDate: "2025-12-31",
    createdAt: "2026-04-24",
    config: { initialCapital: 100000, positionSize: 0.1 },
  },
];

// Settings mock data
export const mockDataSources = [
  { id: "feishu", name: "飞书群聊", enabled: true, connected: true },
  { id: "wechat", name: "微信公众号", enabled: true, connected: false },
  { id: "bilibili", name: "B站视频", enabled: false, connected: false },
  { id: "notebooklm", name: "NotebookLM", enabled: true, connected: true },
];

export const mockKOLConfigs = [
  { id: "kol-1", name: "投研老王", platform: "wechat", enabled: true },
  { id: "kol-2", name: "价值投资张", platform: "bilibili", enabled: true },
  { id: "kol-3", name: "量化小李", platform: "feishu", enabled: true },
];
