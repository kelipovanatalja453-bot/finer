import React, { useRef, useState } from "react";
import { Upload, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

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
      // Allow batch sequentially or grouped. Here we upload sequentially using FormData per file to match the backend easily.
      for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append("file", files[i]);
        formData.append("tier", currentTier);

        const response = await fetch("/api/files", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Upload failed on " + files[i].name);
        }
      }

      setStatus("success");
      onUploadSuccess();
      
      setTimeout(() => setStatus("idle"), 2000);
    } catch (err: unknown) {
      console.error(err);
      setStatus("error");
      setErrorMessage("上传发生错误: " + (err instanceof Error ? err.message : String(err)));
      setTimeout(() => setStatus("idle"), 3000);
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
        "relative rounded-sm border-2 border-transparent transition-all",
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
          "flex items-center gap-2 px-4 py-2 rounded-sm text-[11px] font-bold uppercase tracking-widest transition-all shadow-sm border",
          status === "idle" && "bg-morningstar-red text-white border-morningstar-red hover:bg-red-700",
          status === "uploading" && "bg-stone-100 text-foreground/40 border-stone-200 cursor-not-allowed",
          status === "success" && "bg-emerald-500 text-white border-emerald-500",
          status === "error" && "bg-amber-100 text-amber-700 border-amber-200",
          isDragOver && "pointer-events-none opacity-50"
        )}
      >
        {status === "idle" && (
          <>
            <Upload className="w-3.5 h-3.5" strokeWidth={2} />
            {isDragOver ? "Drop files here" : label}
          </>
        )}
        {status === "uploading" && (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={2} />
            UPLOADING...
          </>
        )}
        {status === "success" && (
          <>
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2} />
            SUCCESS
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="w-3.5 h-3.5" strokeWidth={2} />
            ERROR
          </>
        )}
      </button>

      {status === "error" && errorMessage && (
        <div className="absolute top-full mt-2 left-0 w-48 bg-white border border-stone-200 p-2 shadow-xl z-50 text-[10px] font-bold text-amber-700 rounded-sm">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
