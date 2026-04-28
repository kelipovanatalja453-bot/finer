"use client";

import React, { useState, useEffect, useCallback } from "react";
import { QrCode, RefreshCw, Trash2, FileText, Loader2, CheckCircle2, ExternalLink } from "lucide-react";
import { QRCodeDisplay } from "./QRCodeDisplay";
import { SyncStatus, SyncStatusType } from "./SyncStatus";
import { cn } from "@/lib/utils";

type WeChatAccount = {
  id: string;
  nickname: string;
  avatar_url: string;
  login_time: string;
  is_active: boolean;
};

type WeChatArticle = {
  title: string;
  author: string;
  publish_time: string;
  cover_url: string;
  url: string;
  digest: string;
};

export function WeChatConfig() {
  // Login state
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);
  const [expiresIn, setExpiresIn] = useState<number>(0);
  const [loginSessionId, setLoginSessionId] = useState<string | null>(null);
  const [pollingLogin, setPollingLogin] = useState(false);

  // Accounts state
  const [accounts, setAccounts] = useState<WeChatAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);

  // Articles state
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [articles, setArticles] = useState<WeChatArticle[]>([]);
  const [loadingArticles, setLoadingArticles] = useState(false);

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatusType>("idle");
  const [syncMessage, setSyncMessage] = useState<string>("");
  const [syncProgress, setSyncProgress] = useState<number>(0);
  const [selectedArticles, setSelectedArticles] = useState<Set<string>>(new Set());

  // Load accounts on mount
  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const res = await fetch("/api/wechat/accounts");
      const data = await res.json();
      // 映射后端字段到前端期望的字段
      const mapped = (Array.isArray(data) ? data : []).map((acc: any) => ({
        id: acc.account_id,
        nickname: acc.account_name,
        avatar_url: "",
        login_time: acc.last_sync || "未同步",
        is_active: acc.is_valid,
      }));
      setAccounts(mapped);
      if (mapped.length > 0 && !selectedAccountId) {
        setSelectedAccountId(mapped[0].id);
      }
    } catch (err) {
      console.error("Failed to load accounts:", err);
    } finally {
      setLoadingAccounts(false);
    }
  };

  // Start login process
  const handleStartLogin = async () => {
    setIsLoggingIn(true);
    setQrCodeUrl(null);
    try {
      const res = await fetch("/api/wechat/login", { method: "POST" });
      const data = await res.json();
      // 后端返回 qr_url，前端期望 qr_code_url
      if (data.qr_url) {
        setQrCodeUrl(data.qr_url);
        setExpiresIn(data.expires_in || 300);
        setLoginSessionId(data.session_id);
        setPollingLogin(true);
      }
    } catch (err) {
      console.error("Failed to start login:", err);
    } finally {
      setIsLoggingIn(false);
    }
  };

  // Poll login status
  useEffect(() => {
    if (!pollingLogin || !loginSessionId) return;

    const interval = setInterval(async () => {
      try {
        // 使用路径参数而非查询参数
        const res = await fetch(`/api/wechat/login/status/${loginSessionId}`);
        const data = await res.json();

        if (data.status === "confirmed") {
          setPollingLogin(false);
          setQrCodeUrl(null);
          setLoginSessionId(null);
          setSyncMessage("登录成功！");
          await loadAccounts();
        } else if (data.status === "expired" || data.status === "failed") {
          setPollingLogin(false);
          setQrCodeUrl(null);
          setLoginSessionId(null);
          setSyncMessage(data.error_msg || "登录失败，请重试");
        }
      } catch (err) {
        console.error("Failed to poll login status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pollingLogin, loginSessionId]);

  // Countdown timer
  useEffect(() => {
    if (!pollingLogin || expiresIn <= 0) return;

    const timer = setTimeout(() => {
      setExpiresIn((prev) => prev - 1);
    }, 1000);

    return () => clearTimeout(timer);
  }, [pollingLogin, expiresIn]);

  // Load articles when account is selected
  useEffect(() => {
    if (selectedAccountId) {
      loadArticles(selectedAccountId);
    }
  }, [selectedAccountId]);

  const loadArticles = async (accountId: string) => {
    setLoadingArticles(true);
    try {
      // 使用路径参数而非查询参数
      const res = await fetch(`/api/wechat/articles/${accountId}`);
      const data = await res.json();
      // 映射后端字段到前端期望的字段
      const mapped = (data.articles || []).map((art: any) => ({
        title: art.title,
        author: art.author || "",
        publish_time: art.publish_time || "",
        cover_url: "",
        url: art.content_url || "",
        digest: art.digest || "",
      }));
      setArticles(mapped);
    } catch (err) {
      console.error("Failed to load articles:", err);
    } finally {
      setLoadingArticles(false);
    }
  };

  // Toggle article selection
  const toggleArticle = (url: string) => {
    const next = new Set(selectedArticles);
    if (next.has(url)) {
      next.delete(url);
    } else {
      next.add(url);
    }
    setSelectedArticles(next);
  };

  // Sync selected articles
  const handleSyncArticles = async () => {
    if (!selectedAccountId || selectedArticles.size === 0) return;

    setSyncStatus("syncing");
    setSyncProgress(0);
    setSyncMessage(`正在同步 ${selectedArticles.size} 篇文章...`);

    try {
      // 使用路径参数
      const res = await fetch(`/api/wechat/sync/${selectedAccountId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_articles: null,
          include_images: false,
          trigger_l0: true,
        }),
      });

      const data = await res.json();

      // Simulate progress updates
      for (let i = 0; i <= 100; i += 20) {
        await new Promise((r) => setTimeout(r, 200));
        setSyncProgress(i);
      }

      if (res.ok) {
        setSyncStatus("success");
        setSyncMessage(`成功同步 ${data.synced_count || selectedArticles.size} 篇文章`);
        setSelectedArticles(new Set());
      } else {
        setSyncStatus("error");
        setSyncMessage(data.detail || "同步失败");
      }
    } catch (err) {
      console.error("Sync failed:", err);
      setSyncStatus("error");
      setSyncMessage("同步失败，请重试");
    }
  };

  // Remove account
  const handleRemoveAccount = async (accountId: string) => {
    try {
      await fetch(`/api/wechat/accounts/${accountId}`, { method: "DELETE" });
      await loadAccounts();
      if (selectedAccountId === accountId) {
        setSelectedAccountId(null);
      }
    } catch (err) {
      console.error("Failed to remove account:", err);
    }
  };

  return (
    <div className="space-y-8">
      {/* Login Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--ink-soft)]">
            扫码登录
          </h2>
          <button
            onClick={handleStartLogin}
            disabled={isLoggingIn || pollingLogin}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-widest text-white rounded-sm transition-all",
              isLoggingIn || pollingLogin
                ? "bg-stone-300 cursor-not-allowed"
                : "bg-morningstar-red hover:bg-morningstar-red/90"
            )}
          >
            {isLoggingIn ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <QrCode className="w-4 h-4" />
            )}
            {pollingLogin ? "等待扫码..." : "获取二维码"}
          </button>
        </div>

        <div className="max-w-sm">
          <QRCodeDisplay
            qrCodeUrl={qrCodeUrl}
            isLoading={isLoggingIn}
            expiresIn={expiresIn}
          />
        </div>
      </section>

      {/* Logged Accounts */}
      <section className="space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--ink-soft)]">
          已登录账号 ({accounts.length})
        </h2>

        {loadingAccounts ? (
          <div className="flex items-center justify-center p-8 bg-white border border-stone-200 rounded-sm">
            <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
          </div>
        ) : accounts.length === 0 ? (
          <div className="p-8 bg-stone-50 border border-dashed border-stone-200 rounded-sm text-center">
            <p className="text-sm text-foreground/40">暂无已登录的微信公众号账号</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {accounts.map((account) => (
              <div
                key={account.id}
                className={cn(
                  "flex items-center gap-4 p-4 border rounded-sm transition-all cursor-pointer",
                  selectedAccountId === account.id
                    ? "border-morningstar-red/30 bg-morningstar-red/5 ring-1 ring-morningstar-red/10"
                    : "bg-white border-stone-200 hover:border-morningstar-red/20"
                )}
                onClick={() => setSelectedAccountId(account.id)}
              >
                {/* Avatar */}
                <div className="w-12 h-12 rounded-full bg-stone-100 flex-shrink-0 overflow-hidden">
                  {account.avatar_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={account.avatar_url}
                      alt={account.nickname}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-stone-400 font-bold">
                      {account.nickname.charAt(0)}
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold truncate">{account.nickname}</p>
                  <p className="text-[10px] text-foreground/50 mt-0.5">
                    登录时间: {account.login_time}
                  </p>
                </div>

                {/* Status & Actions */}
                <div className="flex items-center gap-2">
                  {account.is_active && (
                    <span className="flex items-center gap-1 px-2 py-1 bg-green-50 text-green-600 text-[10px] font-bold rounded-full">
                      <CheckCircle2 className="w-3 h-3" />
                      活跃
                    </span>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveAccount(account.id);
                    }}
                    className="p-1.5 hover:bg-red-50 hover:text-morningstar-red rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Articles List */}
      {selectedAccountId && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--ink-soft)]">
              文章列表 ({articles.length})
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => loadArticles(selectedAccountId)}
                disabled={loadingArticles}
                className="p-2 hover:bg-stone-100 rounded transition-colors"
              >
                <RefreshCw
                  className={cn(
                    "w-4 h-4",
                    loadingArticles && "animate-spin"
                  )}
                />
              </button>
              <button
                onClick={handleSyncArticles}
                disabled={selectedArticles.size === 0 || syncStatus === "syncing"}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-widest text-white rounded-sm transition-all",
                  selectedArticles.size === 0 || syncStatus === "syncing"
                    ? "bg-stone-300 cursor-not-allowed"
                    : "bg-[var(--accent-teal)] hover:opacity-90"
                )}
              >
                同步选中 ({selectedArticles.size})
              </button>
            </div>
          </div>

          {/* Sync Status */}
          {syncStatus !== "idle" && (
            <SyncStatus
              status={syncStatus}
              message={syncMessage}
              progress={syncProgress}
            />
          )}

          {loadingArticles ? (
            <div className="flex items-center justify-center p-8 bg-white border border-stone-200 rounded-sm">
              <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
            </div>
          ) : articles.length === 0 ? (
            <div className="p-8 bg-stone-50 border border-dashed border-stone-200 rounded-sm text-center">
              <p className="text-sm text-foreground/40">暂无文章数据</p>
            </div>
          ) : (
            <div className="space-y-3">
              {articles.map((article, idx) => (
                <div
                  key={idx}
                  onClick={() => toggleArticle(article.url)}
                  className={cn(
                    "flex gap-4 p-4 border rounded-sm cursor-pointer transition-all",
                    selectedArticles.has(article.url)
                      ? "border-morningstar-red/30 bg-morningstar-red/5 ring-1 ring-morningstar-red/10"
                      : "bg-white border-stone-200 hover:border-morningstar-red/20"
                  )}
                >
                  {/* Cover */}
                  {article.cover_url && (
                    <div className="w-24 h-16 rounded-sm overflow-hidden flex-shrink-0 bg-stone-100">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={article.cover_url}
                        alt={article.title}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold line-clamp-2">{article.title}</p>
                    <p className="text-xs text-foreground/50 mt-1">
                      {article.author} · {article.publish_time}
                    </p>
                    {article.digest && (
                      <p className="text-xs text-foreground/40 mt-1 line-clamp-1">
                        {article.digest}
                      </p>
                    )}
                  </div>

                  {/* Selection & Link */}
                  <div className="flex items-center gap-2">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="p-1.5 hover:bg-stone-100 rounded transition-colors"
                    >
                      <ExternalLink className="w-4 h-4 text-foreground/50" />
                    </a>
                    {selectedArticles.has(article.url) && (
                      <CheckCircle2 className="w-5 h-5 text-morningstar-red" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}