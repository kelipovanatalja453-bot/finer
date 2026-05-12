"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import {
  BarChart,
  LineChart,
  ScatterChart,
} from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { cn } from "@/lib/utils";

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export type F8EChartOption = EChartsCoreOption;

type BaseEChartProps = {
  option: F8EChartOption;
  height?: number;
  className?: string;
  ariaLabel: string;
};

export function BaseEChart({
  option,
  height = 320,
  className,
  ariaLabel,
}: BaseEChartProps) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);

  useEffect(() => {
    if (!nodeRef.current) return;

    const chart = echarts.init(nodeRef.current, undefined, {
      renderer: "canvas",
      useDirtyRect: true,
    });
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(nodeRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return (
    <div
      ref={nodeRef}
      aria-label={ariaLabel}
      role="img"
      className={cn("w-full", className)}
      style={{ height }}
    />
  );
}
