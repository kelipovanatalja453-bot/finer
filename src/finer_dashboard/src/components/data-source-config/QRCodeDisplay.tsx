"use client";

import React from "react";
import { QrCode, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface QRCodeDisplayProps {
  qrCodeUrl: string | null;
  isLoading: boolean;
  expiresIn?: number;
}

export function QRCodeDisplay({ qrCodeUrl, isLoading, expiresIn }: QRCodeDisplayProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-white border border-stone-200 rounded-sm">
        <Loader2 className="w-12 h-12 animate-spin text-morningstar-red mb-4" />
        <p className="text-sm text-foreground/60">正在生成二维码...</p>
      </div>
    );
  }

  if (!qrCodeUrl) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-stone-50 border border-dashed border-stone-200 rounded-sm">
        <QrCode className="w-16 h-16 text-stone-300 mb-4" strokeWidth={1} />
        <p className="text-sm text-foreground/40">点击下方按钮获取登录二维码</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center p-6 bg-white border border-stone-200 rounded-sm">
      {/* QR Code Image */}
      <div className="relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={qrCodeUrl}
          alt="微信登录二维码"
          className="w-48 h-48 object-contain"
        />
        {expiresIn && expiresIn > 0 && (
          <div className="absolute -top-2 -right-2 bg-morningstar-red text-white text-xs font-bold px-2 py-1 rounded-full shadow-sm">
            {expiresIn}s
          </div>
        )}
      </div>

      {/* Instruction */}
      <div className="mt-4 text-center">
        <p className="text-sm font-bold text-foreground">使用微信扫码登录</p>
        <p className="text-xs text-foreground/50 mt-1">
          打开微信 → 扫一扫 → 确认登录
        </p>
      </div>
    </div>
  );
}