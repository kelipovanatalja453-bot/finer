import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Finer OS — AI-native 投研自动化流水线",
  description:
    "把财经 KOL 的社交媒体内容转化为结构化、可回测、可审计的投资事件。F0-F8 canonical pipeline，证据链可追溯。",
};

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="finer-scrollbar h-full w-full overflow-y-auto bg-background">
      {children}
    </div>
  );
}
