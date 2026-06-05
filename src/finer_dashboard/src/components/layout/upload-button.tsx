import React, { useRef, useState } from "react";
import { Upload, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch, ApiError } from "@/lib/api-client";

interface UploadButtonProps {
  currentTier: string;
  label?: string;
  onUploadSuccess: () => void;
}

export function UploadButton({ currentTier, label = "Import Asset", onUploadSuccess }: UploadButtonProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);

  const performUpload = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;

    setStatus("uploading");
    setErrorMessage("");

    try {
      // Upload sequentially with one FormData per file. Goes through apiFetch so
      // backend errors surface as the canonical envelope (error_code / request_id
      // / fix_hint) instead of a bare HTTP status.
      for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append("file", files[i]);
        formData.append("tier", currentTier);

        await apiFetch("/api/files", {
          method: "POST",
          body: formData,
        });
      }

      // Success here means F0 intake only — the file was archived as a
      // ContentRecord, NOT parsed / standardized. The label reflects that.
      setStatus("success");
      onUploadSuccess();

      setTimeout(() => setStatus("idle"), 2000);
    } catch (err: unknown) {
      console.error(err);
      setStatus("error");
      if (err instanceof ApiError) {
        const parts = [`[${err.code}] ${err.message}`];
        if (err.fixHint) parts.push(err.fixHint);
        if (err.requestId) parts.push(`req: ${err.requestId}`);
        setErrorMessage(parts.join(" — "));
      } else {
        setErrorMessage("上传发生错误: " + (err instanceof Error ? err.message : String(err)));
      }
      setTimeout(() => setStatus("idle"), 5000);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) performUpload(e.target.files);
  };
  
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };
  
  const handleDragLeave = () => {
    setIsDragOver(false);
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files) performUpload(e.dataTransfer.files);
  };

  return (
    <div 
      className={cn(
        "relative shrink-0 rounded-sm border-2 border-transparent transition-all",
        isDragOver ? "border-morningstar-red border-dashed bg-morningstar-red/5 scale-105 z-50 p-1" : ""
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        type="file"
        multiple
        ref={fileInputRef}
        className="hidden"
        onChange={handleFileChange}
      />
      
      <button
        onClick={() => status === "idle" && fileInputRef.current?.click()}
        disabled={status === "uploading"}
        className={cn(
          "flex min-h-9 max-w-[14rem] shrink-0 items-center gap-2 overflow-hidden whitespace-nowrap px-3.5 py-2 rounded-sm text-[11px] font-bold uppercase tracking-widest transition-all shadow-sm border",
          status === "idle" && "bg-morningstar-red text-white border-morningstar-red hover:bg-red-700",
          status === "uploading" && "bg-stone-100 text-foreground/40 border-stone-200 cursor-not-allowed",
          status === "success" && "bg-emerald-500 text-white border-emerald-500",
          status === "error" && "bg-amber-100 text-amber-700 border-amber-200",
          isDragOver && "pointer-events-none opacity-50"
        )}
      >
        {status === "idle" && (
          <>
            <Upload className="w-3.5 h-3.5 shrink-0" strokeWidth={2} />
            <span className="min-w-0 truncate">{isDragOver ? "Drop files here" : label}</span>
          </>
        )}
        {status === "uploading" && (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={2} />
            <span className="min-w-0 truncate">UPLOADING...</span>
          </>
        )}
        {status === "success" && (
          <>
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2} />
            <span className="min-w-0 truncate">已入库 F0</span>
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="w-3.5 h-3.5" strokeWidth={2} />
            <span className="min-w-0 truncate">ERROR</span>
          </>
        )}
      </button>

      {status === "error" && errorMessage && (
        <div className="absolute top-full mt-2 left-0 w-72 bg-white border border-stone-200 p-2 shadow-xl z-50 text-[10px] font-bold text-amber-700 rounded-sm break-words">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
