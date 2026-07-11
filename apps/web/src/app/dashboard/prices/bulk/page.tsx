"use client";

import Link from "next/link";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import {
  PACK_UNITS,
  PRICE_SOURCES,
  dollarsToCents,
  type BulkResult,
  type PackUnit,
  type PriceCreate,
  type PriceSource,
} from "@/lib/prices";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";

interface PreviewRow {
  raw: string;
  parsed?: PriceCreate;
  error?: string;
}

function isPackUnit(v: string): v is PackUnit {
  return (PACK_UNITS as readonly string[]).includes(v);
}

function isPriceSource(v: string): v is PriceSource {
  return PRICE_SOURCES.some((s) => s.value === v);
}

/** Columns: ingredient_id, store_id, pack_desc, pack_qty, pack_unit, price, observed_at?, source */
function parseLine(raw: string): PreviewRow {
  const cells = raw.split("\t").map((c) => c.trim());
  const [ingredientId, storeId, packDesc, packQtyStr, packUnitStr, priceStr, col7, col8] = cells;

  if (ingredientId === undefined || ingredientId.length === 0)
    return { raw, error: "ingredient_id is required" };
  if (storeId === undefined || storeId.length === 0) return { raw, error: "store_id is required" };
  if (packDesc === undefined || packDesc.length === 0)
    return { raw, error: "pack_desc is required" };

  const packQty = Number(packQtyStr);
  if (packQtyStr === undefined || !Number.isFinite(packQty) || packQty <= 0)
    return { raw, error: "pack_qty must be a number > 0" };

  if (packUnitStr === undefined || !isPackUnit(packUnitStr))
    return { raw, error: `pack_unit must be one of ${PACK_UNITS.join(", ")}` };

  const priceCents = priceStr !== undefined ? dollarsToCents(priceStr) : null;
  if (priceCents === null || priceCents <= 0) return { raw, error: "price must be dollars > 0" };

  // observed_at is optional; when 8 columns are present col7 is the date and col8 the source.
  // With 7 columns col7 is the source and there is no date.
  let observedAt: string | undefined;
  let sourceStr: string | undefined;
  if (col8 !== undefined && col8.length > 0) {
    observedAt = col7 !== undefined && col7.length > 0 ? col7 : undefined;
    sourceStr = col8;
  } else {
    sourceStr = col7;
  }

  if (sourceStr === undefined || !isPriceSource(sourceStr))
    return { raw, error: `source must be one of ${PRICE_SOURCES.map((s) => s.value).join(", ")}` };

  const parsed: PriceCreate = {
    ingredient_id: ingredientId,
    store_id: storeId,
    pack_desc: packDesc,
    pack_qty: packQty,
    pack_unit: packUnitStr,
    price_cents: priceCents,
    source: sourceStr,
  };
  if (observedAt !== undefined) parsed.observed_at = observedAt;

  return { raw, parsed };
}

export default function BulkPricesPage() {
  const { toast } = useToast();

  const [text, setText] = useState("");
  const [preview, setPreview] = useState<PreviewRow[] | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);

  const validRows = preview?.filter((r) => r.parsed !== undefined) ?? [];
  const validCount = validRows.length;

  function handlePreview() {
    const rows = text
      .split("\n")
      .map((l) => l.replace(/\r$/, ""))
      .filter((l) => l.trim().length > 0)
      .map(parseLine);
    setPreview(rows);
    setResult(null);
  }

  async function handleSubmit() {
    const entries = validRows.map((r) => r.parsed).filter((p): p is PriceCreate => p !== undefined);
    if (entries.length === 0) return;

    setSubmitting(true);
    const res = await apiPost<BulkResult>("/api/v1/prices/bulk", { entries });
    setSubmitting(false);

    if (!res.ok) {
      toast({
        title: res.problem.title,
        description: res.problem.detail,
        variant: "destructive",
      });
      return;
    }

    setResult(res.data);
    toast({
      title: "Bulk upload complete",
      description: `${res.data.created} created, ${res.data.failed} failed.`,
      variant: res.data.failed > 0 ? "destructive" : "default",
    });
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="space-y-1">
        <Link
          href="/dashboard/ingredients"
          className="text-muted-foreground hover:text-foreground text-sm"
        >
          ← Back to ingredients
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Bulk log prices</h1>
        <p className="text-muted-foreground text-sm">
          Paste tab-separated rows, preview to validate, then submit the valid ones.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Paste rows</CardTitle>
          <CardDescription>
            <span className="font-mono text-xs">
              ingredient_id&nbsp;&nbsp;store_id&nbsp;&nbsp;pack_desc&nbsp;&nbsp;pack_qty&nbsp;&nbsp;pack_unit&nbsp;&nbsp;price(dollars)&nbsp;&nbsp;observed_at(YYYY-MM-DD,
              optional)&nbsp;&nbsp;source
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            placeholder={"ing_123\tstore_9\t20 lb bag\t20\tlb\t52.00\t2026-07-01\tinvoice"}
            className="border-input focus-visible:ring-ring placeholder:text-muted-foreground flex min-h-[200px] w-full rounded-md border bg-transparent px-3 py-2 font-mono text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={handlePreview}>
              Preview
            </Button>
            <Button
              type="button"
              disabled={validCount === 0 || submitting}
              onClick={() => void handleSubmit()}
            >
              {submitting
                ? "Submitting…"
                : `Submit ${validCount} valid row${validCount === 1 ? "" : "s"}`}
            </Button>
          </div>
        </CardContent>
      </Card>

      {preview !== null && (
        <Card>
          <CardHeader>
            <CardTitle>Preview</CardTitle>
            <CardDescription>
              {validCount} of {preview.length} row{preview.length === 1 ? "" : "s"} valid.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
                    <TableHead>Row</TableHead>
                    <TableHead className="w-64">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(() => {
                    // Map each preview row to its position among the valid (submitted) rows,
                    // since the bulk API indexes results by the entries array, not preview rows.
                    let entryIdx = -1;
                    return preview.map((row, i) => {
                      const isValid = row.parsed !== undefined;
                      if (isValid) entryIdx += 1;
                      const submitted =
                        isValid && result !== null
                          ? result.results.find((rr) => rr.index === entryIdx)
                          : undefined;
                      return (
                        <TableRow key={i}>
                          <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                          <TableCell className="max-w-md truncate font-mono text-xs">
                            {row.raw}
                          </TableCell>
                          <TableCell>
                            {submitted !== undefined ? (
                              submitted.ok ? (
                                <div className="space-y-1">
                                  <Badge variant="default">created</Badge>
                                  {submitted.warnings.length > 0 && (
                                    <p className="text-xs text-amber-700 dark:text-amber-300">
                                      {submitted.warnings.join(" ")}
                                    </p>
                                  )}
                                </div>
                              ) : (
                                <div className="space-y-1">
                                  <Badge variant="destructive">failed</Badge>
                                  <p className="text-destructive text-xs">
                                    {submitted.error ?? "Unknown error"}
                                  </p>
                                </div>
                              )
                            ) : row.parsed !== undefined ? (
                              <Badge variant="secondary">ok</Badge>
                            ) : (
                              <span className="text-destructive text-xs">{row.error}</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    });
                  })()}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {result !== null && (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>
              <span className="inline-flex items-center gap-2">
                <Badge variant="default">{result.created} created</Badge>
                {result.failed > 0 && <Badge variant="destructive">{result.failed} failed</Badge>}
              </span>
            </CardDescription>
          </CardHeader>
        </Card>
      )}
    </div>
  );
}
