"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import type { Ingredient, IngredientForecast } from "@/lib/types";
import type { PriceHistory } from "@/lib/prices";

const FORECAST_MONTHS: ReadonlyArray<[string, keyof IngredientForecast]> = [
  ["Jan", "jan"],
  ["Feb", "feb"],
  ["Mar", "mar"],
  ["Apr", "apr"],
  ["May", "may"],
  ["Jun", "jun"],
  ["Jul", "jul"],
  ["Aug", "aug"],
  ["Sep", "sep"],
  ["Oct", "oct"],
  ["Nov", "nov"],
  ["Dec", "dec"],
];
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceHistoryChart } from "@/components/price-history-chart";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { SellersNearby } from "@/components/sellers-nearby";

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

      {/* Sellers within a radius, cheapest first, with add-seller + log-bulk-price. */}
      <SellersNearby
        ingredientId={ingredient.id}
        ingredientName={ingredient.canonical_name_en}
      />

      {ingredient.forecast && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Demand forecast &amp; sourcing</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {FORECAST_MONTHS.some(([, k]) => ingredient.forecast?.[k] != null) && (
              <div className="overflow-x-auto">
                <div className="flex min-w-[600px] gap-1 text-center text-xs">
                  {FORECAST_MONTHS.map(([label, k]) => (
                    <div key={k} className="flex-1">
                      <div className="text-muted-foreground">{label}</div>
                      <div className="font-medium">{ingredient.forecast?.[k] ?? "—"}</div>
                    </div>
                  ))}
                  <div className="flex-1">
                    <div className="text-muted-foreground">Yr</div>
                    <div className="font-semibold">{ingredient.forecast.annual ?? "—"}</div>
                  </div>
                </div>
              </div>
            )}
            {ingredient.forecast.g_ml_per_serving != null && (
              <p className="text-muted-foreground text-xs">
                ~{ingredient.forecast.g_ml_per_serving} g/ml per serving
              </p>
            )}
            {ingredient.forecast.recommended_vendor && (
              <div>
                <div className="text-muted-foreground text-xs">Recommended vendor</div>
                <div>{ingredient.forecast.recommended_vendor}</div>
              </div>
            )}
            {ingredient.forecast.vendor_website && (
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {ingredient.forecast.vendor_website
                  .split("·")
                  .map((w) => w.trim())
                  .filter((w) => w.length > 0)
                  .map((host) => (
                    <a
                      key={host}
                      href={host.startsWith("http") ? host : `https://${host}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      {host}
                    </a>
                  ))}
              </div>
            )}
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
