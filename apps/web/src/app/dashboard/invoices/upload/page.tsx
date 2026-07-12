"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2, UploadCloud } from "lucide-react";
import {
  getInvoiceStatus,
  isProcessing,
  uploadInvoice,
} from "@/lib/invoices";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

export default function UploadInvoicePage() {
  const t = useTranslations("invoices");
  const router = useRouter();
  const { toast } = useToast();

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Object-URL thumbnail for image files; revoke on change/unmount.
  useEffect(() => {
    if (file && file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreviewUrl(null);
  }, [file]);

  function pickFile(next: File | null) {
    if (next) setFile(next);
  }

  async function pollUntilReady(id: string) {
    // Poll /status until extraction finishes (needs_review / failed / committed).
    for (;;) {
      const res = await getInvoiceStatus(id);
      if (!res.ok) {
        await new Promise((r) => setTimeout(r, 2500));
        continue;
      }
      const { status } = res.data;
      if (status === "failed") {
        setBusy(false);
        setStatusText(null);
        toast({
          title: t("uploadFailedTitle"),
          description: t("uploadFailedBody"),
          variant: "destructive",
        });
        return;
      }
      if (!isProcessing(status)) {
        router.push(`/dashboard/invoices/${id}/review`);
        return;
      }
      setStatusText(t("statusHint.extracting"));
      await new Promise((r) => setTimeout(r, 2500));
    }
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    setStatusText(t("statusHint.uploading"));
    const res = await uploadInvoice(file);
    if (!res.ok) {
      setBusy(false);
      setStatusText(null);
      toast({
        title: res.problem.title,
        description: res.problem.detail,
        variant: "destructive",
      });
      return;
    }
    setStatusText(t("statusHint.extracting"));
    await pollUntilReady(res.data.id);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-1">
        <Link
          href="/dashboard/invoices"
          className="text-muted-foreground hover:text-foreground text-sm"
        >
          ← {t("title")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">{t("uploadTitle")}</h1>
        <p className="text-muted-foreground">{t("uploadSubtitle")}</p>
      </div>

      <Card>
        <CardContent className="space-y-4 py-6">
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pickFile(e.dataTransfer.files?.[0] ?? null);
            }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragOver ? "border-primary bg-accent/50" : "border-muted-foreground/30"
            }`}
          >
            <UploadCloud className="text-muted-foreground h-8 w-8" />
            <p className="font-medium">{t("dropzoneTitle")}</p>
            <p className="text-muted-foreground text-sm">{t("dropzoneHint")}</p>
            <input
              ref={inputRef}
              type="file"
              accept="image/*,application/pdf"
              capture="environment"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {file && (
            <div className="flex items-center gap-3 rounded-md border p-3">
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewUrl}
                  alt={file.name}
                  className="h-16 w-16 rounded object-cover"
                />
              ) : (
                <div className="bg-muted flex h-16 w-16 items-center justify-center rounded text-xs uppercase">
                  {t("pdfLabel")}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{file.name}</p>
                <p className="text-muted-foreground text-xs">
                  {(file.size / 1024).toFixed(0)} KB
                </p>
              </div>
              {!busy && (
                <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
                  {t("clearFile")}
                </Button>
              )}
            </div>
          )}

          {statusText && (
            <p className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              {statusText}
            </p>
          )}

          <div className="flex justify-end">
            <Button disabled={!file || busy} onClick={() => void submit()}>
              {busy ? t("processing") : t("uploadCta")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
