"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  GitCompare,
  LineChart,
  Settings,
  Database,
} from "lucide-react";

const navItems = [
  { href: "/", label: "工作台", icon: LayoutDashboard },
  { href: "/kol", label: "KOL", icon: Users },
  { href: "/kol/compare", label: "对比", icon: GitCompare },
  { href: "/backtest", label: "回测", icon: LineChart },
  { href: "/settings", label: "设置", icon: Settings },
];

export function Header() {
  const pathname = usePathname();

  // Determine active state
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-stone-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <div className="container flex h-14 items-center">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 mr-8">
          <div className="w-8 h-8 bg-morningstar-red rounded flex items-center justify-center">
            <Database className="w-4 h-4 text-white" strokeWidth={2} />
          </div>
          <span className="font-bold text-lg tracking-tight">Finer OS</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors",
                  active
                    ? "bg-stone-100 text-foreground"
                    : "text-foreground/60 hover:text-foreground hover:bg-stone-50"
                )}
              >
                <Icon className="w-4 h-4" strokeWidth={1.5} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right side - can add user menu, etc */}
        <div className="flex-1 flex justify-end items-center gap-4">
          <span className="text-xs text-foreground/40 font-medium">
            AI-native 投研流水线
          </span>
        </div>
      </div>
    </header>
  );
}
