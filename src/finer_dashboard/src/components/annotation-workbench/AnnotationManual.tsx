"use client";

import React from "react";
import { X } from "lucide-react";

export function AnnotationManual({ onClose }: { onClose: () => void }) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[90] flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative h-full w-full max-w-md overflow-y-auto bg-white shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-stone-200 bg-white px-5 py-3">
          <div className="text-sm font-semibold">标注手册</div>
          <button onClick={onClose} className="rounded p-1 hover:bg-stone-100">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-5 p-5 text-xs leading-relaxed text-foreground/80">
          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              1. 内容类型判断
            </h3>
            <ul className="list-disc space-y-1 pl-4">
              <li>
                图片占位 / OCR 缺失 → <kbd className="rounded border bg-stone-100 px-1">X</kbd>{" "}
                排除 (image_placeholder)
              </li>
              <li>上下文不足 → 排除 (insufficient_context)</li>
              <li>非投研内容 → 排除 (non_investment)</li>
              <li>投研相关 → 继续 ↓</li>
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              2. 可提取性判断
            </h3>
            <ul className="list-disc space-y-1 pl-4">
              <li>
                无明确标的、方向模糊 → <kbd className="rounded border bg-stone-100 px-1">A</kbd>{" "}
                弃权 (watchlist + NONE)
              </li>
              <li>有标的但证据弱 → 弃权 (watchlist + ticker)</li>
              <li>标的明确、方向可判 → 标 Gold ↓</li>
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              3. 标注 Gold
            </h3>
            <ol className="list-decimal space-y-1.5 pl-4">
              <li>
                <strong>Ticker</strong>: 点击实体 chip 自动填入；手填时用证券代码（TME、0700.HK），不用中文名
              </li>
              <li>
                <strong>Direction</strong>: 键盘{" "}
                <kbd className="rounded border bg-stone-100 px-1">1</kbd>-
                <kbd className="rounded border bg-stone-100 px-1">5</kbd> 快捷键
              </li>
              <li>
                <strong>Action Chain</strong>: 价位只填原文出现的数字——点击原文中高亮数字可直接填入
              </li>
              <li>
                <strong>Conviction</strong>: 根据证据可溯性选择
              </li>
            </ol>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              Conviction 档位
            </h3>
            <table className="w-full text-left">
              <tbody className="divide-y divide-stone-100">
                <tr>
                  <td className="py-1.5 pr-2 font-mono font-bold text-green-700">0.8</td>
                  <td>标的 + 价位均在原文可溯</td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 font-mono font-bold text-blue-700">0.6</td>
                  <td>标的可溯，无明确价位</td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 font-mono font-bold text-amber-700">0.45</td>
                  <td>涨幅/比例（如「20% 空间」）≠ 价位</td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 font-mono font-bold text-red-700">0.3</td>
                  <td>标的存疑或需验证</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              v3 新能力
            </h3>
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <strong>上下文</strong>：证据卡顶/底「展开上文/下文」加载邻近消息；
                「并入证据」的消息导出时拼进 eval 样本（模型与你看到同样输入），并计入可溯校验
              </li>
              <li>
                <strong>多标的</strong>：一段话讲多个标的时，主标的之外填「次要标的」，评测 match-any 计分
              </li>
              <li>
                <strong>实体候补</strong>：ticker 告警框里一键提交实体库候补，人工 review 后进 registry
              </li>
              <li>
                <strong>KOL 速记</strong>：选中原文文字 → 「存入 KOL Profile」，按风格/纪律/偏好/战绩分类沉淀
              </li>
              <li>
                <strong>行情对照</strong>：左栏自动查实体在内容日期附近的 A 股行情（需本地库已同步），验证目标价量级
              </li>
              <li>
                <strong>模型初稿</strong>：存在 drafts.jsonl 时可「采纳并修正」——先形成自己的判断再看，避免锚定
              </li>
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              常见陷阱
            </h3>
            <ul className="list-disc space-y-1 pl-4">
              <li>「修复空间 20%」是涨幅比例，不是目标价</li>
              <li>「腾讯音乐」→ TME (US)，不是 1698.HK —— 看实体 chip</li>
              <li>expected_abstain 和 bullish/bearish 方向矛盾时会弹出告警</li>
              <li>价位填入后如果原文不存在会标红提示</li>
              <li>空 action_chain 合法（纯方向观点 / 弃权项可不填）</li>
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              快捷键
            </h3>
            <table className="w-full text-left">
              <tbody className="divide-y divide-stone-100">
                <tr>
                  <td className="py-1 pr-3 font-mono">← →</td>
                  <td>上/下一条</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">S</td>
                  <td>跳到下一条待标</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">1-5</td>
                  <td>选方向</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">A</td>
                  <td>应弃权</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">X</td>
                  <td>样本无效</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">Enter</td>
                  <td>提交</td>
                </tr>
                <tr>
                  <td className="py-1 pr-3 font-mono">?</td>
                  <td>打开/关闭本手册</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              Pair 抽检
            </h3>
            <ul className="list-disc space-y-1 pl-4">
              <li>差异字段高亮，相同字段折叠——只看不同的部分</li>
              <li>
                <kbd className="rounded border bg-stone-100 px-1">A</kbd> 合格 /{" "}
                <kbd className="rounded border bg-stone-100 px-1">E</kbd> 修正 /{" "}
                <kbd className="rounded border bg-stone-100 px-1">R</kbd> 剔除
              </li>
              <li>修正模式下编辑的 JSON 会实时校验格式</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
