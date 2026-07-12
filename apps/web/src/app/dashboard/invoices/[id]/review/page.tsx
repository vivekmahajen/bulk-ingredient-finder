"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2, Loader2, Plus, ZoomIn, ZoomOut } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { dollars } from "@/lib/compare";
import { dollarsToCents } from "@/lib/prices";
import { searchIngredients } from "@/lib/search";
import { useEnumLabels } from "@/lib/i18n-labels";
import type { Store } from "@/lib/stores";
import {
  commitInvoice,
  confidenceBucket,
  getInvoice,
  getInvoiceStatus,
  isProcessing,
  LINE_PACK_UNITS,
  patchLine,
  rejectInvoice,
  type InvoiceLineRead,
  type InvoiceRead,
} from "@/lib/invoices";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";

/** Sum of `extended_cents` over currently-accepted (non-excluded) lines. */
function acceptedTotalCents(lines: InvoiceLineRead[]): number {
  return lines
    .filter((l) => l.match_status !== "excluded")
    .reduce((sum, l) => sum + (l.extended_cents ?? 0), 0);
}

export default function ReviewInvoicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("invoices");
  const labels = useEnumLabels();
  const router = useRouter();
  const { toast } = useToast();

  const [invoice, setInvoice] = useState<InvoiceRead | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<string>("");
  const [zoom, setZoom] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [waiting, setWaiting] = useState(false);

  const reload = useCallback(async () => {
    const res = await getInvoice(id);
    if (res.ok) {
      setInvoice(res.data);
      setStoreId((prev) => prev || res.data.store_id || res.data.store_guess?.store_id || "");
    }
    return res.ok ? res.data : null;
  }, [id]);

  useEffect(() => {
    void reload();
    void apiGet<Store[]>("/api/v1/stores").then((res) => {
      if (res.ok) setStores(res.data);
    });
  }, [reload]);

  // If extraction is still running, poll /status until it settles, then reload.
  useEffect(() => {
    if (!invoice || !isProcessing(invoice.status)) return;
    setWaiting(true);
    let active = true;
    const tick = async () => {
      const res = await getInvoiceStatus(id);
      if (!active) return;
      if (res.ok && !isProcessing(res.data.status)) {
        setWaiting(false);
        await reload();
        return;
      }
      timer = setTimeout(() => void tick(), 2500);
    };
    let timer = setTimeout(() => void tick(), 2500);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [invoice, id, reload]);

  const updateLine = useCallback((updated: InvoiceLineRead) => {
    setInvoice((inv) =>
      inv
        ? { ...inv, lines: inv.lines.map((l) => (l.id === updated.id ? updated : l)) }
        : inv,
    );
  }, []);

  if (!invoice) {
    return <p className="text-muted-foreground text-sm">{t("loading")}</p>;
  }

  if (waiting || isProcessing(invoice.status)) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
        <p className="font-medium">{t("extractingTitle")}</p>
        <p className="text-muted-foreground text-sm">{t("extractingBody")}</p>
      </div>
    );
  }

  if (invoice.status === "failed") {
    return (
      <div className="space-y-4">
        <Link
          href="/dashboard/invoices"
          className="text-muted-foreground hover:text-foreground text-sm"
        >
          ← {t("title")}
        </Link>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4">
          <p className="font-medium">{t("uploadFailedTitle")}</p>
          <p className="text-muted-foreground text-sm">
            {invoice.extraction_error ?? t("uploadFailedBody")}
          </p>
        </div>
      </div>
    );
  }

  const lines = invoice.lines;
  const accepted = lines.filter((l) => l.match_status !== "excluded");
  const computed = acceptedTotalCents(lines);
  const stated = invoice.stated_total_cents;
  const totalsMatch = stated != null ? Math.abs(stated - computed) <= 1 : null;
  const hasLowConfidenceAccepted = accepted.some((l) => l.confidence < 0.7);
  const committed = invoice.status === "committed";

  async function doCommit() {
    setConfirmOpen(false);
    setCommitting(true);
    const lineIds = invoice!.lines
      .filter((l) => l.match_status !== "excluded")
      .map((l) => l.id);
    const res = await commitInvoice(id, { store_id: storeId, line_ids: lineIds });
    setCommitting(false);
    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return;
    }
    toast({
      title: t("committedToast"),
      description: t("committedToastBody", {
        created: res.data.created,
        skipped: res.data.skipped_duplicates,
        excluded: res.data.excluded,
      }),
    });
    router.push("/dashboard/invoices");
  }

  function onCommitClick() {
    if (!storeId) return;
    if (totalsMatch === false || hasLowConfidenceAccepted) {
      setConfirmOpen(true);
    } else {
      void doCommit();
    }
  }

  async function onReject() {
    const res = await rejectInvoice(id);
    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return;
    }
    toast({ title: t("rejectedToast") });
    router.push("/dashboard/invoices");
  }

  function onAcceptHighConfidence() {
    const count = lines.filter(
      (l) => l.match_status !== "excluded" && l.confidence >= 0.9,
    ).length;
    toast({ title: t("acceptedHighConfidence", { count }) });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard/invoices"
          className="text-muted-foreground hover:text-foreground text-sm"
        >
          ← {t("title")}
        </Link>
        {committed && <Badge variant="default">{t("status.committed")}</Badge>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {/* Left: the invoice image */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <div className="overflow-auto rounded-lg border bg-muted/30 p-2">
            {invoice.signed_image_url ? (
              <button
                type="button"
                onClick={() => setZoom((z) => !z)}
                className="block w-full cursor-zoom-in"
                aria-label={t("toggleZoom")}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={invoice.signed_image_url}
                  alt={t("invoiceImageAlt")}
                  className={`mx-auto origin-top transition-transform ${
                    zoom ? "scale-[1.75]" : "scale-100"
                  }`}
                />
              </button>
            ) : (
              <p className="text-muted-foreground p-8 text-center text-sm">{t("noImage")}</p>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-muted-foreground text-xs">{t("clickToZoom")}</p>
            <Button variant="ghost" size="sm" onClick={() => setZoom((z) => !z)}>
              {zoom ? <ZoomOut className="h-4 w-4" /> : <ZoomIn className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {/* Right: header + line table */}
        <div className="space-y-5">
          {/* Header */}
          <div className="space-y-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                {invoice.vendor_name_raw ?? t("unknownVendor")}
              </h1>
              <p className="text-muted-foreground text-sm">
                {invoice.invoice_date ?? t("noDate")}
                {invoice.invoice_number ? ` · #${invoice.invoice_number}` : ""}
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">{t("store")}</label>
              <div className="flex items-center gap-2">
                <Select value={storeId} onValueChange={setStoreId} disabled={committed}>
                  <SelectTrigger className="max-w-xs">
                    <SelectValue placeholder={t("selectStore")} />
                  </SelectTrigger>
                  <SelectContent>
                    {stores.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {invoice.store_guess && storeId === invoice.store_guess.store_id && (
                  <span className="text-muted-foreground text-xs">{t("guessed")}</span>
                )}
              </div>
            </div>

            {/* Totals */}
            <div className="flex flex-wrap items-center gap-4 rounded-md border p-3 text-sm">
              <div>
                <span className="text-muted-foreground">{t("statedTotal")}: </span>
                <span className="font-medium">
                  {stated != null ? dollars(stated) : t("noDate")}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">{t("computedTotal")}: </span>
                <span className="font-medium">{dollars(computed)}</span>
              </div>
              {totalsMatch === true && (
                <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-4 w-4" />
                  {t("totalsMatch")}
                </span>
              )}
              {totalsMatch === false && (
                <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-4 w-4" />
                  {t("totalsMismatch")}
                </span>
              )}
            </div>
          </div>

          {/* Line table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("colItem")}</TableHead>
                  <TableHead>{t("colPack")}</TableHead>
                  <TableHead>{t("colUnitPrice")}</TableHead>
                  <TableHead>{t("colPerBase")}</TableHead>
                  <TableHead>{t("colMatch")}</TableHead>
                  <TableHead className="text-right">{t("colActions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.map((line) => (
                  <LineRow
                    key={line.id}
                    invoiceId={id}
                    line={line}
                    disabled={committed}
                    labels={labels}
                    onUpdated={updateLine}
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          {!committed && (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onAcceptHighConfidence}>
                  {t("acceptHighConfidence")}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => void onReject()}>
                  {t("reject")}
                </Button>
              </div>
              <Button disabled={!storeId || committing} onClick={onCommitClick}>
                {committing ? t("committing") : t("commit")}
              </Button>
            </div>
          )}
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("confirmCommitTitle")}</DialogTitle>
            <DialogDescription>
              {totalsMatch === false && <span className="block">{t("confirmMismatch")}</span>}
              {hasLowConfidenceAccepted && <span className="block">{t("confirmLowConfidence")}</span>}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t("cancel")}
            </Button>
            <Button onClick={() => void doCommit()}>{t("commitAnyway")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------------------------------------------------------- LineRow */

interface LineRowProps {
  invoiceId: string;
  line: InvoiceLineRead;
  disabled: boolean;
  labels: ReturnType<typeof useEnumLabels>;
  onUpdated: (line: InvoiceLineRead) => void;
}

function LineRow({ invoiceId, line, disabled, labels, onUpdated }: LineRowProps) {
  const t = useTranslations("invoices");
  const { toast } = useToast();

  const [packDesc, setPackDesc] = useState(line.pack_desc ?? "");
  const [packQty, setPackQty] = useState(line.pack_qty != null ? String(line.pack_qty) : "");
  const [price, setPrice] = useState(
    line.unit_price_cents != null ? (line.unit_price_cents / 100).toFixed(2) : "",
  );
  const [caseCount, setCaseCount] = useState(
    line.case_count != null ? String(line.case_count) : "",
  );

  const excluded = line.match_status === "excluded";
  const bucket = confidenceBucket(line.confidence);
  const bucketVariant =
    bucket === "high" ? "secondary" : bucket === "medium" ? "warning" : "destructive";

  async function patch(body: Parameters<typeof patchLine>[2]) {
    const res = await patchLine(invoiceId, line.id, body);
    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return;
    }
    onUpdated(res.data);
  }

  function savePackDesc() {
    if (packDesc !== (line.pack_desc ?? "")) void patch({ pack_desc: packDesc || null });
  }
  function savePackQty() {
    const v = packQty.trim() === "" ? null : Number(packQty);
    if (v !== line.pack_qty && (v === null || Number.isFinite(v))) void patch({ pack_qty: v });
  }
  function savePrice() {
    const cents = price.trim() === "" ? null : dollarsToCents(price);
    if (cents !== line.unit_price_cents) void patch({ unit_price_cents: cents });
  }
  function saveCaseCount() {
    const v = caseCount.trim() === "" ? null : Number(caseCount);
    if (v !== line.case_count && (v === null || Number.isFinite(v))) void patch({ case_count: v });
  }

  function toggleExclude() {
    const next = excluded
      ? line.matched_ingredient_id
        ? "manual"
        : "unmatched"
      : "excluded";
    void patch({ match_status: next });
  }

  return (
    <TableRow className={excluded ? "opacity-50" : ""}>
      {/* Item: raw_text (original script, prominent) + description_en */}
      <TableCell className="max-w-[16rem] align-top">
        <p className="text-base font-medium" lang={line.raw_lang ?? undefined}>
          {line.raw_text}
        </p>
        {line.description_en && line.description_en !== line.raw_text && (
          <p className="text-muted-foreground text-xs">{line.description_en}</p>
        )}
        {line.brand && <p className="text-muted-foreground text-xs">{line.brand}</p>}
        <div className="mt-1 flex items-center gap-1">
          <Badge variant={bucketVariant} className="text-[10px]">
            {t("confidenceLabel", { level: labels.confidence(bucket) })}
          </Badge>
          {line.is_credit && (
            <Badge variant="outline" className="text-[10px]">
              {t("credit")}
            </Badge>
          )}
        </div>
      </TableCell>

      {/* Pack: desc, qty, unit */}
      <TableCell className="align-top">
        <div className="flex w-40 flex-col gap-1">
          <Input
            value={packDesc}
            disabled={disabled}
            onChange={(e) => setPackDesc(e.target.value)}
            onBlur={savePackDesc}
            placeholder={t("packDesc")}
            className="h-8"
          />
          <div className="flex gap-1">
            <Input
              value={packQty}
              disabled={disabled}
              inputMode="decimal"
              onChange={(e) => setPackQty(e.target.value)}
              onBlur={savePackQty}
              placeholder={t("qty")}
              className="h-8 w-16"
            />
            <Select
              value={line.pack_unit ?? ""}
              disabled={disabled}
              onValueChange={(v) => void patch({ pack_unit: v })}
            >
              <SelectTrigger className="h-8">
                <SelectValue placeholder={t("unit")} />
              </SelectTrigger>
              <SelectContent>
                {LINE_PACK_UNITS.map((u) => (
                  <SelectItem key={u} value={u}>
                    {labels.unit(u)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </TableCell>

      {/* Unit price (dollars) + case count */}
      <TableCell className="align-top">
        <div className="flex w-24 flex-col gap-1">
          <Input
            value={price}
            disabled={disabled}
            inputMode="decimal"
            onChange={(e) => setPrice(e.target.value)}
            onBlur={savePrice}
            placeholder="$"
            className="h-8"
          />
          <Input
            value={caseCount}
            disabled={disabled}
            inputMode="numeric"
            onChange={(e) => setCaseCount(e.target.value)}
            onBlur={saveCaseCount}
            placeholder={t("caseCount")}
            className="h-8"
          />
        </div>
      </TableCell>

      {/* $/base preview */}
      <TableCell className="align-top whitespace-nowrap text-sm">
        {line.unit_price_per_base_cents != null && line.base_unit ? (
          <span className="font-medium">
            {dollars(line.unit_price_per_base_cents)}/{labels.unit(line.base_unit)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>

      {/* Match */}
      <TableCell className="align-top">
        <MatchPicker invoiceId={invoiceId} line={line} disabled={disabled} onUpdated={onUpdated} />
      </TableCell>

      {/* Actions */}
      <TableCell className="align-top text-right">
        <Button
          variant={excluded ? "outline" : "ghost"}
          size="sm"
          disabled={disabled}
          onClick={toggleExclude}
        >
          {excluded ? t("include") : t("exclude")}
        </Button>
      </TableCell>
    </TableRow>
  );
}

/* ------------------------------------------------------------ MatchPicker */

interface MatchOption {
  id: string;
  name: string;
}

interface MatchPickerProps {
  invoiceId: string;
  line: InvoiceLineRead;
  disabled: boolean;
  onUpdated: (line: InvoiceLineRead) => void;
}

function MatchPicker({ invoiceId, line, disabled, onUpdated }: MatchPickerProps) {
  const t = useTranslations("invoices");
  const { toast } = useToast();

  const matchedFromCandidates =
    line.matched_ingredient_id != null
      ? line.candidates.find((c) => c.ingredient_id === line.matched_ingredient_id)
      : undefined;
  const [matchedName, setMatchedName] = useState<string | null>(
    matchedFromCandidates?.canonical_name_en ?? null,
  );

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MatchOption[]>([]);
  const [searching, setSearching] = useState(false);
  const [creating, setCreating] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced ingredient search; before typing, fall back to the AI candidates.
  useEffect(() => {
    const q = query.trim();
    if (q.length === 0) {
      setResults(line.candidates.map((c) => ({ id: c.ingredient_id, name: c.canonical_name_en })));
      setSearching(false);
      return;
    }
    setSearching(true);
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void searchIngredients(q).then((resp) => {
        setSearching(false);
        setResults((resp?.results ?? []).map((r) => ({ id: r.id, name: r.canonical_name_en })));
      });
    }, 200);
    return () => {
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
  }, [query, line.candidates]);

  async function select(opt: MatchOption) {
    const res = await patchLine(invoiceId, line.id, {
      matched_ingredient_id: opt.id,
      match_status: "manual",
    });
    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return;
    }
    setMatchedName(opt.name);
    onUpdated(res.data);
    setOpen(false);
    setQuery("");
  }

  async function createIngredient() {
    setCreating(true);
    const created = await apiPost<{ id: string; canonical_name_en: string }>(
      "/api/v1/ingredients",
      { display_name: line.raw_text, source_lang: line.raw_lang ?? undefined },
    );
    setCreating(false);
    if (!created.ok) {
      toast({
        title: created.problem.title,
        description: created.problem.detail,
        variant: "destructive",
      });
      return;
    }
    await select({ id: created.data.id, name: created.data.canonical_name_en });
  }

  const label =
    matchedName ??
    (line.matched_ingredient_id ? t("matched") : t(`matchStatus.${line.match_status}`));

  return (
    <div className="relative w-48">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        className="w-full justify-start font-normal"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="truncate">{label}</span>
      </Button>

      {open && !disabled && (
        <div className="bg-popover text-popover-foreground absolute z-50 mt-1 w-64 rounded-md border p-1 shadow-md">
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchIngredient")}
            className="mb-1 h-8"
          />
          <div className="max-h-56 overflow-y-auto">
            {searching ? (
              <p className="text-muted-foreground px-2 py-1.5 text-sm">{t("searching")}</p>
            ) : results.length === 0 ? (
              <p className="text-muted-foreground px-2 py-1.5 text-sm">{t("noMatches")}</p>
            ) : (
              results.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="hover:bg-accent hover:text-accent-foreground w-full rounded-sm px-2 py-1.5 text-left text-sm"
                  onClick={() => void select(r)}
                >
                  {r.name}
                </button>
              ))
            )}
          </div>
          <button
            type="button"
            disabled={creating}
            className="hover:bg-accent hover:text-accent-foreground mt-1 flex w-full items-center gap-1.5 rounded-sm border-t px-2 py-1.5 text-left text-sm"
            onClick={() => void createIngredient()}
          >
            <Plus className="h-3.5 w-3.5" />
            {creating ? t("creating") : t("createIngredient", { name: line.raw_text })}
          </button>
        </div>
      )}
    </div>
  );
}
