"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { apiPost } from "@/lib/api";
import { CATEGORIES, DEFAULT_UNITS, FREQUENCIES } from "@/lib/types";
import {
  parseIngredientTable,
  type IngredientCreate,
  type PreviewRow,
} from "@/lib/ingredient-import";
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

interface BulkRowResult {
  index: number;
  ok: boolean;
  id?: string | null;
  canonical_name_en?: string | null;
  needs_review: boolean;
  error?: string | null;
}

interface BulkResult {
  created: number;
  failed: number;
  results: BulkRowResult[];
}

const FREQ_VALUES = FREQUENCIES.map((f) => f.value);

export default function BulkIngredientsPage() {
  const { toast } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [preview, setPreview] = useState<PreviewRow[] | null>(null);
  const [headerMapped, setHeaderMapped] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);

  const validRows = preview?.filter((r) => r.parsed !== undefined) ?? [];
  const validCount = validRows.length;

  function runPreview(source: string) {
    const { headerMapped: mapped, rows } = parseIngredientTable(source);
    setHeaderMapped(mapped);
    setPreview(rows);
    setResult(null);
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setText(content);
    runPreview(content);
    if (fileInput.current) fileInput.current.value = ""; // allow re-selecting the same file
  }

  async function handleSubmit() {
    const items = validRows
      .map((r) => r.parsed)
      .filter((p): p is IngredientCreate => p !== undefined);
    if (items.length === 0) return;

    setSubmitting(true);
    const res = await apiPost<BulkResult>("/api/v1/ingredients/bulk", { items });
    setSubmitting(false);

    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return;
    }

    setResult(res.data);
    toast({
      title: "Bulk upload complete",
      description: `${res.data.created} added, ${res.data.failed} failed.`,
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
        <h1 className="text-2xl font-semibold tracking-tight">Bulk add ingredients</h1>
        <p className="text-muted-foreground text-sm">
          Upload a CSV/TSV or paste rows from a spreadsheet, preview to validate, then submit. Names
          in any language are auto-translated and made searchable.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload or paste</CardTitle>
          <CardDescription>
            <span className="block">
              Has a header row with <span className="font-medium">Ingredient</span> and{" "}
              <span className="font-medium">Category</span>? Columns are auto-mapped —{" "}
              <span className="font-medium">Category</span>,{" "}
              <span className="font-medium">Order cadence</span>,{" "}
              <span className="font-medium">Purchase as</span>,{" "}
              <span className="font-medium">Recommended vendor</span>, and{" "}
              <span className="font-medium">Website</span> are recognized, and the monthly forecast
              (Jan–Dec, Annual) + per-serving size are captured. Only the ingredient name is
              required — everything else is optional.
            </span>
            <span className="mt-1 block">
              No header? Use:{" "}
              <span className="font-mono text-xs">
                name&nbsp;&nbsp;category&nbsp;&nbsp;unit&nbsp;&nbsp;frequency?&nbsp;&nbsp;language?&nbsp;&nbsp;par_level?
              </span>
            </span>
            <span className="text-muted-foreground mt-1 block text-xs">
              categories: {CATEGORIES.join(", ")} · units: {DEFAULT_UNITS.join(", ")} · cadence:{" "}
              {FREQ_VALUES.join(", ")}
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values,text/plain"
            className="hidden"
            onChange={(e) => void handleFile(e)}
          />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            placeholder={
              "Ingredient\tCategory\tPurchase as\tOrder cadence\nChicken (boneless)\tProtein\t40 lb case\t2×/week\nWhole milk\tDairy\tGallon\t2×/week"
            }
            className="border-input focus-visible:ring-ring placeholder:text-muted-foreground flex min-h-[200px] w-full rounded-md border bg-transparent px-3 py-2 font-mono text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => fileInput.current?.click()}>
              Choose file…
            </Button>
            <Button type="button" variant="outline" onClick={() => runPreview(text)}>
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
              {validCount} of {preview.length} row{preview.length === 1 ? "" : "s"} valid
              {headerMapped ? " · columns auto-mapped from header" : ""}.
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
                    // since the bulk API indexes results by the items array, not preview rows.
                    let itemIdx = -1;
                    return preview.map((row, i) => {
                      const isValid = row.parsed !== undefined;
                      if (isValid) itemIdx += 1;
                      const submitted =
                        isValid && result !== null
                          ? result.results.find((rr) => rr.index === itemIdx)
                          : undefined;
                      return (
                        <TableRow key={i}>
                          <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                          <TableCell className="max-w-md truncate font-mono text-xs">
                            {row.raw}
                          </TableCell>
                          <TableCell>
                            {!isValid ? (
                              <Badge variant="destructive">{row.error}</Badge>
                            ) : submitted ? (
                              submitted.ok ? (
                                <span className="flex items-center gap-2">
                                  <Badge>Added</Badge>
                                  <span className="text-muted-foreground text-xs">
                                    {submitted.canonical_name_en}
                                  </span>
                                  {submitted.needs_review && (
                                    <Badge variant="warning">Needs review</Badge>
                                  )}
                                </span>
                              ) : (
                                <Badge variant="destructive">{submitted.error}</Badge>
                              )
                            ) : (
                              <Badge variant="secondary">Valid</Badge>
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
    </div>
  );
}
