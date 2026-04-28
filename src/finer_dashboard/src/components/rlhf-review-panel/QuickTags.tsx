"use client";

import React from "react";
import { Tag, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface QuickTagsProps {
  selected: string[];
  onChange: (tags: string[]) => void;
}

const PRESET_TAGS = [
  // 质量标签
  { label: "提取准确", category: "quality", color: "green" },
  { label: "需要修正", category: "quality", color: "amber" },
  { label: "信息不全", category: "quality", color: "red" },
  { label: "标注有误", category: "quality", color: "red" },

  // 内容标签
  { label: "多标的", category: "content", color: "blue" },
  { label: "时间敏感", category: "content", color: "blue" },
  { label: "观点冲突", category: "content", color: "amber" },
  { label: "语言模糊", category: "content", color: "amber" },

  // 来源标签
  { label: "来源可靠", category: "source", color: "green" },
  { label: "二手信息", category: "source", color: "blue" },
  { label: "传闻", category: "source", color: "amber" },
  { label: "待验证", category: "source", color: "amber" }
];

const CATEGORY_LABELS: Record<string, string> = {
  quality: "质量",
  content: "内容",
  source: "来源"
};

const COLOR_CLASSES: Record<string, { base: string; selected: string }> = {
  green: {
    base: "border-green-200 bg-green-50 text-green-700 hover:border-green-300",
    selected: "border-green-500 bg-green-100 text-green-800"
  },
  blue: {
    base: "border-blue-200 bg-blue-50 text-blue-700 hover:border-blue-300",
    selected: "border-blue-500 bg-blue-100 text-blue-800"
  },
  amber: {
    base: "border-amber-200 bg-amber-50 text-amber-700 hover:border-amber-300",
    selected: "border-amber-500 bg-amber-100 text-amber-800"
  },
  red: {
    base: "border-red-200 bg-red-50 text-red-700 hover:border-red-300",
    selected: "border-red-500 bg-red-100 text-red-800"
  }
};

export function QuickTags({ selected, onChange }: QuickTagsProps) {
  const [customTag, setCustomTag] = React.useState("");

  const toggleTag = (tagLabel: string) => {
    if (selected.includes(tagLabel)) {
      onChange(selected.filter(t => t !== tagLabel));
    } else {
      onChange([...selected, tagLabel]);
    }
  };

  const addCustomTag = () => {
    const trimmed = customTag.trim();
    if (trimmed && !selected.includes(trimmed)) {
      onChange([...selected, trimmed]);
      setCustomTag("");
    }
  };

  const removeTag = (tagLabel: string) => {
    onChange(selected.filter(t => t !== tagLabel));
  };

  const groupedTags = PRESET_TAGS.reduce((acc, tag) => {
    if (!acc[tag.category]) acc[tag.category] = [];
    acc[tag.category].push(tag);
    return acc;
  }, {} as Record<string, typeof PRESET_TAGS>);

  return (
    <div className="rounded-xl border border-[rgba(95,67,40,0.12)] bg-white/80 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[rgba(95,67,40,0.08)] bg-[rgba(99,76,55,0.02)] flex items-center gap-2">
        <Tag className="w-4 h-4 text-morningstar-red" strokeWidth={1.5} />
        <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/70">
          快捷标签
        </h3>
        {selected.length > 0 && (
          <span className="ml-auto text-[10px] font-medium text-foreground/50 bg-stone-100 px-2 py-0.5 rounded-full">
            {selected.length} 已选
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Preset tags grouped by category */}
        {Object.entries(groupedTags).map(([category, tags]) => (
          <div key={category}>
            <div className="text-[10px] font-medium text-foreground/40 uppercase tracking-wider mb-2">
              {CATEGORY_LABELS[category] || category}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag) => {
                const isSelected = selected.includes(tag.label);
                const colors = COLOR_CLASSES[tag.color];

                return (
                  <button
                    key={tag.label}
                    onClick={() => toggleTag(tag.label)}
                    className={cn(
                      "px-2.5 py-1 text-[11px] font-medium rounded-full border transition-all",
                      isSelected
                        ? colors.selected
                        : colors.base
                    )}
                  >
                    {tag.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {/* Custom tag input */}
        <div>
          <div className="text-[10px] font-medium text-foreground/40 uppercase tracking-wider mb-2">
            自定义标签
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={customTag}
              onChange={(e) => setCustomTag(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addCustomTag()}
              placeholder="输入自定义标签..."
              className="flex-1 px-3 py-1.5 text-xs bg-white border border-stone-300 focus:border-morningstar-red focus:ring-1 focus:ring-morningstar-red/20 rounded-sm outline-none transition-all"
            />
            <button
              onClick={addCustomTag}
              disabled={!customTag.trim()}
              className="px-3 py-1.5 text-xs font-medium text-white bg-morningstar-red hover:bg-red-700 disabled:bg-stone-300 disabled:cursor-not-allowed rounded-sm transition-colors"
            >
              添加
            </button>
          </div>
        </div>

        {/* Selected tags */}
        {selected.length > 0 && (
          <div>
            <div className="text-[10px] font-medium text-foreground/40 uppercase tracking-wider mb-2">
              已选标签
            </div>
            <div className="flex flex-wrap gap-1.5">
              {selected.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-full bg-morningstar-red/10 text-morningstar-red border border-morningstar-red/20"
                >
                  {tag}
                  <button
                    onClick={() => removeTag(tag)}
                    className="hover:bg-morningstar-red/20 rounded-full p-0.5 -mr-1 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}