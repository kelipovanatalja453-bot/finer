/**
 * Opinion Timeline Components
 *
 * 观点时间线可视化组件，用于展示和筛选历史观点。
 *
 * 主要组件:
 * - OpinionTimeline: 主时间线容器
 * - TimelineNode: 单个观点节点
 * - TimelineFilter: 筛选器
 * - OpinionDetailModal: 详情弹窗
 *
 * 使用示例:
 * ```tsx
 * import { OpinionTimeline } from "@/components/opinion-timeline";
 *
 * function TimelinePage() {
 *   return (
 *     <OpinionTimeline
 *       initialFilters={{ timeRange: "1M" }}
 *       onOpinionClick={(opinion) => console.log("Selected:", opinion)}
 *     />
 *   );
 * }
 * ```
 */

export { OpinionTimeline } from "./OpinionTimeline";
export { TimelineNode } from "./TimelineNode";
export { TimelineFilter } from "./TimelineFilter";
export { OpinionDetailModal } from "./OpinionDetailModal";

// 类型导出
export type {
  TimelineOpinion,
  ActionStep,
  OpinionDirection,
  VerificationStatus,
  TimelineData,
  OpinionTimelineProps,
} from "./OpinionTimeline";

export type {
  TimeRange,
  TimelineFilters,
} from "./TimelineFilter";
