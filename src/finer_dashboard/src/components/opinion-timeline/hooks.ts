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

const hooks = {
  useTimelineData,
  useTimelineScroll,
  useDragScroll,
  useKeyboardNavigation,
};

export default hooks;
