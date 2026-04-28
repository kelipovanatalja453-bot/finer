import { AppShell } from "@/components/layout/app-shell";

export default function KOLLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
