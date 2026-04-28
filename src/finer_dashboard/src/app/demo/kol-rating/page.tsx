"use client";

import React from "react";
import { KOLRatingCard } from "@/components/kol-rating-card";

export default function KOLRatingCardDemo() {
  return (
    <div className="min-h-screen bg-[#f3efe7] p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="mb-8">
          <h1 className="text-2xl font-bold text-foreground mb-2">
            KOL 评价卡片组件演示
          </h1>
          <p className="text-sm text-foreground/60">
            参考晨星网基金经理评价风格设计，展示 KOL 的综合评分、维度分析、业绩时间线和最近观点。
          </p>
        </header>

        {/* Full card */}
        <section>
          <h2 className="text-lg font-bold text-foreground mb-4">完整卡片</h2>
          <KOLRatingCard kolId="demo_001" />
        </section>

        {/* Compact card */}
        <section>
          <h2 className="text-lg font-bold text-foreground mb-4">紧凑模式</h2>
          <KOLRatingCard kolId="demo_001" compact />
        </section>

        {/* Card without timeline */}
        <section>
          <h2 className="text-lg font-bold text-foreground mb-4">
            简化模式（无时间线）
          </h2>
          <KOLRatingCard kolId="demo_001" showTimeline={false} />
        </section>

        {/* Card without opinions */}
        <section>
          <h2 className="text-lg font-bold text-foreground mb-4">
            简化模式（无最近观点）
          </h2>
          <KOLRatingCard kolId="demo_001" showOpinions={false} />
        </section>
      </div>
    </div>
  );
}