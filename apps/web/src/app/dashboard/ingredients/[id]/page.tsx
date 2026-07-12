"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import type { Ingredient } from "@/lib/types";
import type { PriceHistory } from "@/lib/prices";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceHistoryChart } from "@/components/price-history-chart";
import { LogPriceDialog } from "@/components/log-price-dialog";

interface CheapestNow {
  store: string;
  dollars: number;
  baseQty: number;
  perUnit: number;
  baseUnit: string;
  stale: boolean;
  observedAt: string;
}

function computeCheapestNow(history: PriceHistory): CheapestNow | null {
  let best: CheapestNow | null = null;
  for (const s of history.series) {
    const latest = [...s.points].reverse().find((p) => p.unit_price_cents != null);
    if (!latest || latest.unit_price_cents == null) continue;
    const perUnit = latest.unit_price_cents / 100;
    const dollars = latest.price_cents / 100;
    const baseQty = latest.price_cents / latest.unit_price_cents; // cents / (cents/base) = base
    if (!best || perUnit < best.perUnit) {
      best = {
        store: s.store_name,
        dollars,
        baseQty,
        perUnit,
        baseUnit: latest.base_unit,
        stale: latest.stale,
        observedAt: latest.observed_at,
      };
    }
  }
  return best;
}

export default function IngredientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [ingredient, setIngredient] = useState<Ingredient | null>(null);
  const [history, setHistory] = useState<PriceHistory | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(() => {
    Promise.all([
      apiGet<Ingredient>(`/api/v1/ingredients/${id}`),
      apiGet<PriceHistory>(`/api/v1/ingredients/${id}/price-history`),
    ]).then(([ing, hist]) => {
      if (ing.ok) setIngredient(ing.data);
      else if (ing.status === 404) setNotFound(true);
      if (hist.ok) setHistory(hist.data);
    });
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (notFound) return <p className="text-muted-foreground text-sm">Ingredient not found.</p>;
  if (!ingredient) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const cheapest = history ? computeCheapestNow(history) : null;

  return (
    <div className="space-y-6">
      <Link href="/dashboard/ingredients" className="text-muted-foreground text-sm hover:underline">
        ← All ingredients
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{ingredient.canonical_name_en}</h1>
            {ingredient.needs_review && <Badge variant="warning">Needs review</Badge>}
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            {ingredient.display_name} · {ingredient.category} ·{" "}
            {ingredient.purchase_frequency.replace("_", " ")}
          </p>
          {ingredient.aliases.length > 0 && (
            <p className="text-muted-foreground mt-1 text-xs">
              also searchable as: {ingredient.aliases.map((a) => a.alias).join(", ")}
            </p>
          )}
        </div>
        <LogPriceDialog
          ingredientId={ingredient.id}
          ingredientName={ingredient.canonical_name_en}
          onLogged={load}
          trigger={<Button>Log a price</Button>}
        />
      </div>

      {/* Cheapest now — the math is shown explicitly. Never hide the date/source. */}
      {cheapest ? (
        <Card>
          <CardContent className="py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <span className="text-muted-foreground text-sm">Cheapest now</span>
                <div className="text-xl font-semibold">
                  ${cheapest.perUnit.toFixed(2)}/{cheapest.baseUnit} @ {cheapest.store}
                </div>
                <div className="text-muted-foreground text-xs">
                  ${cheapest.dollars.toFixed(2)} / {cheapest.baseQty.toFixed(2)} {cheapest.baseUnit}{" "}
                  = ${cheapest.perUnit.toFixed(2)}/{cheapest.baseUnit}
                </div>
              </div>
              <div className="text-muted-foreground text-right text-xs">
                observed {cheapest.observedAt}
                {cheapest.stale && (
                  <>
                    {" "}
                    <Badge variant="warning">stale</Badge>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="text-muted-foreground py-4 text-sm">
            No prices logged yet.{" "}
            <LogPriceDialog
              ingredientId={ingredient.id}
              ingredientName={ingredient.canonical_name_en}
              onLogged={load}
              trigger={
                <button className="underline" type="button">
                  Log the first one
                </button>
              }
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Price history</CardTitle>
        </CardHeader>
        <CardContent>
          {history && history.series.length > 0 ? (
            <PriceHistoryChart series={history.series} />
          ) : (
            <p className="text-muted-foreground text-sm">No price history yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
