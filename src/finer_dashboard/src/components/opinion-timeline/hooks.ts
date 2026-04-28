/**
 * Opinion Timeline Hooks
 *
 * 自定义 hooks 用于观点时间线组件
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type { TimelineOpinion, TimelineData } from "./OpinionTimeline";
import type { TimelineFilters } from "./TimelineFilter";

// ============================================
// 类型定义
// ============================================

interface UseTimelineDataOptions {
  filters: TimelineFilters;
  pageSize?: number;
  autoLoad?: boolean;
}

interface UseTimelineDataReturn {
  opinions: TimelineOpinion[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
  reset: () => void;
}

// ============================================
// 模拟数据生成
// ============================================

function generateMockOpinions(count: number, startIndex: number = 0): TimelineOpinion[] {
  const tickers = [
    { symbol: "NVDA", name: "英伟达" },
    { symbol: "AAPL", name: "苹果" },
    { symbol: "TSLA", name: "特斯拉" },
    { symbol: "AMD", name: "超微半导体" },
    { symbol: "MSFT", name: "微软" },
    { symbol: "GOOGL", name: "谷歌" },
    { symbol: "AMZN", name: "亚马逊" },
    { symbol: "META", name: "Meta" },
  ];

  const authors = ["分析师张三", "李四", "王五", "财通证券", "中信证券", "高盛研究"];
  const platforms = ["财通证券", "中信证券", "高盛研究", "摩根士丹利", "内部研究"];

  const directions: ("bullish" | "bearish" | "neutral")[] = ["bullish", "bearish", "neutral"];
  const verificationStatuses: ("success" | "failed" | "pending")[] = ["success", "failed", "pending"];

  const actionVerbs = ["回调至", "突破", "站稳", "跌破", "反弹至"];
  const priceRanges = [
    { low: "100", high: "120" },
    { low: "150", high: "180" },
    { low: "200", high: "250" },
    { low: "300", high: "350" },
    { low: "450", high: "500" },
  ];

  return Array.from({ length: count }, (_, i) => {
    const ticker = tickers[Math.floor(Math.random() * tickers.length)];
    const direction = directions[Math.floor(Math.random() * directions.length)];
    const status = verificationStatuses[Math.floor(Math.random() * verificationStatuses.length)];

    const baseTime = Date.now() - (startIndex + i) * 24 * 60 * 60 * 1000 * (0.5 + Math.random());

    const hasActionChain = Math.random() > 0.3;

    return {
      id: `opinion-${startIndex + i}`,
      timestamp: new Date(baseTime).toISOString(),
      ticker: ticker.symbol,
      tickerName: ticker.name,
      direction,
      confidence: 0.5 + Math.random() * 0.5,
      verificationStatus: status,
      priceChange: status !== "pending" ? (Math.random() - 0.5) * 30 : undefined,
      holdingDays: status !== "pending" ? Math.floor(Math.random() * 30) + 1 : undefined,
      sourceText: generateMockSourceText(ticker.symbol, direction),
      author: authors[Math.floor(Math.random() * authors.length)],
      platform: platforms[Math.floor(Math.random() * platforms.length)],
      actionChain: hasActionChain ? generateMockActionChain() : undefined,
      rlhfStatus: Math.random() > 0.5 ? "pending" : Math.random() > 0.5 ? "reviewed" : "skipped",
      rlhfRating: Math.random() > 0.5 ? Math.floor(Math.random() * 5) + 1 : undefined,
    };
  });
}

function generateMockSourceText(ticker: string, direction: string): string {
  const templates = [
    `分析师认为${ticker}在当前市场环境下具有较好的投资价值，建议关注后续走势。`,
    `${ticker}近期表现强劲，技术面显示有进一步上涨空间，可考虑逢低布局。`,
    `从基本面分析来看，${ticker}估值处于合理区间，短期看${direction === "bullish" ? "多" : direction === "bearish" ? "空" : "中性"}。`,
    `${ticker}发布了超预期的财报，市场反应积极，建议关注后续催化剂。`,
    `考虑到宏观经济环境，${ticker}面临一定压力，建议谨慎操作。`,
  ];
  return templates[Math.floor(Math.random() * templates.length)];
}

function generateMockActionChain() {
  const actionTypes = ["watch", "long", "short", "close_long"] as const;
  const count = Math.floor(Math.random() * 2) + 1;

  return Array.from({ length: count }, (_, i) => ({
    id: `step-${i}`,
    actionType: actionTypes[Math.floor(Math.random() * actionTypes.length)],
    triggerCondition: i === 0 ? "突破前高" : undefined,
    targetPriceLow: String(100 + Math.floor(Math.random() * 50)),
    targetPriceHigh: String(150 + Math.floor(Math.random() * 100)),
  }));
}

// ============================================
// Hook: useTimelineData
// ============================================

export function useTimelineData(options: UseTimelineDataOptions): UseTimelineDataReturn {
  const { filters, pageSize = 20, autoLoad = true } = options;

  const [opinions, setOpinions] = useState<TimelineOpinion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [cursor, setCursor] = useState(0);

  const abortControllerRef = useRef<AbortController | null>(null);

  const loadData = useCallback(async (reset = false) => {
    // 取消之前的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      // 构建查询参数
      const params = new URLSearchParams();
      params.set("limit", String(pageSize));
      params.set("timeRange", filters.timeRange || "1M");
      if (filters.tickers.length > 0) {
        params.set("tickers", filters.tickers.join(","));
      }
      if (filters.directions.length > 0) {
        params.set("directions", filters.directions.join(","));
      }
      if (filters.kols.length > 0) {
        params.set("kols", filters.kols.join(","));
      }
      if (!reset && cursor > 0) {
        params.set("cursor", String(cursor));
      }

      // 调用真实 API
      const response = await fetch(`/api/opinions/timeline?${params.toString()}`, {
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: TimelineData = await response.json();

      setOpinions(prev => reset ? data.opinions : [...prev, ...data.opinions]);
      setCursor(data.nextCursor ? parseInt(data.nextCursor) : cursor + pageSize);
      setHasMore(data.hasMore);
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [cursor, pageSize, filters]);

  const loadMore = useCallback(async () => {
    if (!loading && hasMore) {
      await loadData(false);
    }
  }, [loading, hasMore, loadData]);

  const refresh = useCallback(async () => {
    setCursor(0);
    await loadData(true);
  }, [loadData]);

  const reset = useCallback(() => {
    setOpinions([]);
    setCursor(0);
    setError(null);
    setHasMore(true);
  }, []);

  // 自动加载
  useEffect(() => {
    if (autoLoad) {
      reset();
      loadData(true);
    }
  }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    opinions,
    loading,
    error,
    hasMore,
    loadMore,
    refresh,
    reset,
  };
}

// ============================================
// Hook: useTimelineScroll
// ============================================

interface UseTimelineScrollOptions {
  onLoadMore?: () => void;
  hasMore?: boolean;
  threshold?: number;
}

export function useTimelineScroll(options: UseTimelineScrollOptions) {
  const { onLoadMore, hasMore = true, threshold = 200 } = options;
  const containerRef = useRef<HTMLDivElement>(null);

  const handleScroll = useCallback(() => {
    if (!containerRef.current || !hasMore) return;

    const { scrollLeft, scrollWidth, clientWidth } = containerRef.current;
    const distanceToEnd = scrollWidth - scrollLeft - clientWidth;

    if (distanceToEnd < threshold) {
      onLoadMore?.();
    }
  }, [onLoadMore, hasMore, threshold]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  return containerRef;
}

// ============================================
// Hook: useDragScroll
// ============================================

export function useDragScroll() {
  const ref = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const startPosRef = useRef({ x: 0, scrollLeft: 0 });

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!ref.current) return;
    setIsDragging(true);
    startPosRef.current = {
      x: e.pageX,
      scrollLeft: ref.current.scrollLeft,
    };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging || !ref.current) return;
    e.preventDefault();
    const walk = (e.pageX - startPosRef.current.x) * 1.5;
    ref.current.scrollLeft = startPosRef.current.scrollLeft - walk;
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return {
    ref,
    isDragging,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onMouseLeave: handleMouseUp,
    },
  };
}

// ============================================
// Hook: useKeyboardNavigation
// ============================================

interface UseKeyboardNavigationOptions {
  onPrevious?: () => void;
  onNext?: () => void;
  onSelect?: () => void;
  onEscape?: () => void;
  enabled?: boolean;
}

export function useKeyboardNavigation(options: UseKeyboardNavigationOptions) {
  const { onPrevious, onNext, onSelect, onEscape, enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          onPrevious?.();
          break;
        case "ArrowRight":
          e.preventDefault();
          onNext?.();
          break;
        case "Enter":
        case " ":
          e.preventDefault();
          onSelect?.();
          break;
        case "Escape":
          onEscape?.();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, onPrevious, onNext, onSelect, onEscape]);
}

export default {
  useTimelineData,
  useTimelineScroll,
  useDragScroll,
  useKeyboardNavigation,
};
