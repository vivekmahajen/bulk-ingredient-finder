"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import {
  isProcessing,
  listInvoices,
  type InvoiceListItem,
  type InvoiceStatus,
} from "@/lib/invoices";
import { dollars } from "@/lib/compare";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const STATUS_VARIANT: Record<InvoiceStatus, "default" | "secondary" | "warning" | "destructive"> = {
  uploaded: "secondary",
  extracting: "secondary",
  needs_review: "warning",
  committed: "default",
  failed: "destructive",
  rejected: "secondary",
};

function StatusChip({ status, label }: { status: InvoiceStatus; label: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status]} className={status === "extracting" ? "animate-pulse" : ""}>
      {label}
    </Badge>
  );
}

export default function InvoicesPage() {
  const t = useTranslations("invoices");
  const [invoices, setInvoices] = useState<InvoiceListItem[] | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const res = await listInvoices({ page_size: 100 });
    if (res.ok) setInvoices(res.data.items);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // While any row is still extracting, refresh the whole list every 2.5s.
  const anyProcessing = (invoices ?? []).some((i) => isProcessing(i.status));
  useEffect(() => {
    if (!anyProcessing) {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(() => void load(), 2500);
    return () => {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [anyProcessing, load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button asChild>
          <Link href="/dashboard/invoices/upload">＋ {t("upload")}</Link>
        </Button>
      </div>

      {invoices === null ? (
        <p className="text-muted-foreground text-sm">{t("loading")}</p>
      ) : invoices.length === 0 ? (
        <Card>
          <CardContent className="space-y-2 py-10 text-center">
            <p className="text-lg font-medium">{t("emptyTitle")}</p>
            <p className="text-muted-foreground">{t("emptyBody")}</p>
            <div className="pt-2">
              <Button asChild>
                <Link href="/dashboard/invoices/upload">＋ {t("upload")}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {invoices.map((inv) => (
            <Card key={inv.id} className="hover:border-foreground/30 transition-colors">
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <Link href={`/dashboard/invoices/${inv.id}/review`} className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">
                      {inv.vendor_name_raw ?? t("unknownVendor")}
                    </span>
                    <StatusChip status={inv.status} label={t(`status.${inv.status}`)} />
                    {inv.totals_match === false && (
                      <span
                        className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
                        title={t("totalsMismatch")}
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {t("totalsMismatch")}
                      </span>
                    )}
                    {inv.totals_match === true && (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    )}
                  </div>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {inv.invoice_date ?? t("noDate")}
                    {" · "}
                    {t("lineCount", { count: inv.line_count })}
                  </p>
                </Link>
                <div className="flex shrink-0 items-center gap-3">
                  {inv.stated_total_cents != null && (
                    <span className="text-sm font-medium">{dollars(inv.stated_total_cents)}</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
