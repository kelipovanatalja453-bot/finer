/**
 * Custom hook for loading mock data with loading state.
 * Simulates API latency for development.
 */

import { useState, useEffect, useCallback } from "react";

interface UseMockDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  reload: () => void;
}

export function useMockData<T>(
  mockData: T,
  delay: number = 300
): UseMockDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadData = useCallback(() => {
    setLoading(true);
    setError(null);

    const timer = setTimeout(() => {
      try {
        setData(mockData);
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Unknown error"));
      } finally {
        setLoading(false);
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [mockData, delay]);

  useEffect(() => {
    const cleanup = loadData();
    return cleanup;
  }, [loadData]);

  return { data, loading, error, reload: loadData };
}

/**
 * Hook for async data fetching with error handling.
 * Use this when transitioning from mock to real API.
 */
export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = []
): UseMockDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Unknown error"));
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/use-memo
  }, deps);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return { data, loading, error, reload: loadData };
}
