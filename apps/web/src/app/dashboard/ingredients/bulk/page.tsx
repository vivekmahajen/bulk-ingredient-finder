"use client";

import Link from "next/link";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import {
  CATEGORIES,
  DEFAULT_UNITS,
  FREQUENCIES,
  type Category,
  type DefaultUnit,
  type PurchaseFrequency,
} from "@/lib/types";
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

interface IngredientCreate {
  display_name: string;
  source_lang?: string | null;
  category: Category;
  default_unit: DefaultUnit;
  purchase_frequency: PurchaseFrequency;
  par_level?: number | null;
}

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

interface PreviewRow {
  raw: string;
  parsed?: IngredientCreate;
  error?: string;
}

const FREQ_VALUES = FREQUENCIES.map((f) => f.value);

function isCategory(v: string): v is Category {
  return (CATEGORIES as readonly string[]).includes(v);
}
function isUnit(v: string): v is DefaultUnit {
  return (DEFAULT_UNITS as readonly string[]).includes(v);
}
function isFrequency(v: string): v is PurchaseFrequency {
  return (FREQ_VALUES as readonly string[]).includes(v);
}

/** Columns: name, category, unit, frequency?, language?, par_level? (tab-separated) */
function parseLine(raw: string): PreviewRow {
  const cells = raw.split("\t").map((c) => c.trim());
  const [name, categoryStr, unitStr, freqStr, langStr, parStr] = cells;

  if (name === undefined || name.length === 0) return { raw, error: "name is required" };
  if (categoryStr === undefined || !isCategory(categoryStr))
    return { raw, error: `category must be one of ${CATEGORIES.join(", ")}` };
  if (unitStr === undefined || !isUnit(unitStr))
    return { raw, error: `unit must be one of ${DEFAULT_UNITS.join(", ")}` };

  let frequency: PurchaseFrequency = "weekly";
  if (freqStr !== undefined && freqStr.length > 0) {
    if (!isFrequency(freqStr))
      return { raw, error: `frequency must be one of ${FREQ_VALUES.join(", ")}` };
    frequency = freqStr;
  }

  let parLevel: number | null = null;
  if (parStr !== undefined && parStr.length > 0) {
    const n = Number(parStr);
    if (!Number.isFinite(n) || n < 0) return { raw, error: "par_level must be a number ≥ 0" };
    parLevel = n;
  }

  const parsed: IngredientCreate = {
    display_name: name,
    category: categoryStr,
    default_unit: unitStr,
    purchase_frequency: frequency,
    par_level: parLevel,
  };
  if (langStr !== undefined && langStr.length > 0) parsed.source_lang = langStr;

  return { raw, parsed };
}

export default function BulkIngredientsPage() {
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
          Paste tab-separated rows, preview to validate, then submit the valid ones. Names in any
          language are auto-translated and made searchable.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Paste rows</CardTitle>
          <CardDescription>
            <span className="font-mono text-xs">
              name&nbsp;&nbsp;category&nbsp;&nbsp;unit&nbsp;&nbsp;frequency(optional)&nbsp;&nbsp;language(optional)&nbsp;&nbsp;par_level(optional)
            </span>
            <br />
            <span className="text-xs">
              category: {CATEGORIES.join(", ")} · unit: {DEFAULT_UNITS.join(", ")} · frequency:{" "}
              {FREQ_VALUES.join(", ")} (default weekly)
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            placeholder={
              "Basmati Rice\tstaple\tkg\tweekly\nहल्दी\tspice\tkg\tmonthly\thi\nPaneer\tdairy\tkg\ttwice_weekly\t\t5"
            }
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
