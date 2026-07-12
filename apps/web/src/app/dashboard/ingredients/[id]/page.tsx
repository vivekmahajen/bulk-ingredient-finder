"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { apiGet } from "@/lib/api";
import { useEnumLabels } from "@/lib/i18n-labels";
import type { Ingredient, IngredientForecast } from "@/lib/types";
import type { PriceHistory } from "@/lib/prices";

const FORECAST_MONTHS: ReadonlyArray<keyof IngredientForecast> = [
  "jan",
  "feb",
  "mar",
  "apr",
  "may",
  "jun",
  "jul",
  "aug",
  "sep",
  "oct",
  "nov",
  "dec",
];
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceHistoryChart } from "@/components/price-history-chart";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { SellersNearby } from "@/components/sellers-nearby";

export default function IngredientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("ingredientDetail");
  const ti = useTranslations("ingredients");
  const labels = useEnumLabels();
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

  if (notFound) return <p className="text-muted-foreground text-sm">{t("notFound")}</p>;
  if (!ingredient) return <p className="text-muted-foreground text-sm">{t("loading")}</p>;

  return (
    <div className="space-y-6">
      <Link href="/dashboard/ingredients" className="text-muted-foreground text-sm hover:underline">
        ← {t("allIngredients")}
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{ingredient.canonical_name_en}</h1>
            {ingredient.needs_review && <Badge variant="warning">{ti("needsReview")}</Badge>}
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            {ingredient.display_name} · {labels.category(ingredient.category)} ·{" "}
            {labels.frequency(ingredient.purchase_frequency)}
          </p>
          {ingredient.aliases.length > 0 && (
            <p className="text-muted-foreground mt-1 text-xs">
              {ti("alsoSearchableAs")} {ingredient.aliases.map((a) => a.alias).join(", ")}
            </p>
          )}
        </div>
        <LogPriceDialog
          ingredientId={ingredient.id}
          ingredientName={ingredient.canonical_name_en}
          onLogged={load}
          trigger={<Button>{t("logPrice")}</Button>}
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
            <CardTitle className="text-base">{t("forecastTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {FORECAST_MONTHS.some((k) => ingredient.forecast?.[k] != null) && (
              <div className="overflow-x-auto">
                <div className="flex min-w-[600px] gap-1 text-center text-xs">
                  {FORECAST_MONTHS.map((k) => (
                    <div key={k} className="flex-1">
                      <div className="text-muted-foreground">{labels.month(k)}</div>
                      <div className="font-medium">{ingredient.forecast?.[k] ?? "—"}</div>
                    </div>
                  ))}
                  <div className="flex-1">
                    <div className="text-muted-foreground">{labels.month("year")}</div>
                    <div className="font-semibold">{ingredient.forecast.annual ?? "—"}</div>
                  </div>
                </div>
              </div>
            )}
            {ingredient.forecast.g_ml_per_serving != null && (
              <p className="text-muted-foreground text-xs">
                {t("perServing", { amount: ingredient.forecast.g_ml_per_serving })}
              </p>
            )}
            {ingredient.forecast.recommended_vendor && (
              <div>
                <div className="text-muted-foreground text-xs">{t("recommendedVendor")}</div>
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
          <CardTitle className="text-base">{t("priceHistory")}</CardTitle>
        </CardHeader>
        <CardContent>
          {history && history.series.length > 0 ? (
            <PriceHistoryChart series={history.series} />
          ) : (
            <p className="text-muted-foreground text-sm">{t("noPriceHistory")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
