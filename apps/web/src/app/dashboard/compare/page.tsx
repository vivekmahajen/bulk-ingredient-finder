"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { useEnumLabels } from "@/lib/i18n-labels";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  CompareResponse,
  IngredientCompare,
  StoreOption,
  RADIUS_PRESETS,
  FREQUENCIES,
  dollars,
  fetchCompare,
  fetchFrequencyRun,
} from "@/lib/compare";
import { searchIngredients } from "@/lib/search";

interface SelectedIngredient {
  id: string;
  name: string;
}

interface SearchResult {
  id: string;
  canonical_name_en: string;
  matched_text: string;
}

const CONFIDENCE_VARIANT: Record<StoreOption["confidence"], "default" | "secondary" | "outline"> = {
  high: "default",
  medium: "secondary",
  low: "outline",
};

function ConfidenceBadge({ option }: { option: StoreOption }) {
  const t = useTranslations("compare");
  const labels = useEnumLabels();
  return (
    <span className="inline-flex items-center gap-1">
      <Badge variant={CONFIDENCE_VARIANT[option.confidence]}>
        {labels.confidence(option.confidence)}
      </Badge>
      {option.age_days > 90 ? <Badge variant="warning">{t("stale")}</Badge> : null}
    </span>
  );
}

function optionMeta(option: StoreOption, t: ReturnType<typeof useTranslations>): string {
  const parts: string[] = [];
  parts.push(
    `${new Date(option.observed_at).toLocaleDateString()} · ${t("daysAgo", { days: option.age_days })}`,
  );
  if (option.distance_km != null)
    parts.push(t("kmValue", { km: option.distance_km.toFixed(0) }));
  return parts.join(" · ");
}

/** Group ingredients by the store that wins their cheapest option. */
function groupByWinningStore(
  ingredients: IngredientCompare[],
): Array<{
  storeName: string;
  items: Array<{ ingredient: IngredientCompare; winner: StoreOption }>;
}> {
  const groups = new Map<string, Array<{ ingredient: IngredientCompare; winner: StoreOption }>>();
  for (const ingredient of ingredients) {
    const winner = ingredient.options[0];
    if (!winner) continue;
    const key = winner.store_name;
    const bucket = groups.get(key) ?? [];
    bucket.push({ ingredient, winner });
    groups.set(key, bucket);
  }
  return Array.from(groups.entries()).map(([storeName, items]) => ({ storeName, items }));
}

export default function ComparePage() {
  const t = useTranslations("compare");
  const labels = useEnumLabels();
  const [selected, setSelected] = useState<SelectedIngredient[]>([]);
  const [radiusKm, setRadiusKm] = useState<number | null>(25);
  const [includeDelivery, setIncludeDelivery] = useState<boolean>(true);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const [query, setQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchOpen, setSearchOpen] = useState<boolean>(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length === 0) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      const res = await searchIngredients(q);
      const hits: SearchResult[] = res
        ? res.results.map((r) => ({
            id: r.id,
            canonical_name_en: r.canonical_name_en,
            matched_text: r.matched_text,
          }))
        : [];
      setSearchResults(hits);
      setSearchOpen(hits.length > 0);
    }, 200);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const addIngredient = useCallback((hit: SearchResult) => {
    setSelected((prev) =>
      prev.some((s) => s.id === hit.id)
        ? prev
        : [...prev, { id: hit.id, name: hit.canonical_name_en }],
    );
    setQuery("");
    setSearchResults([]);
    setSearchOpen(false);
  }, []);

  const removeIngredient = useCallback((id: string) => {
    setSelected((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const runCompare = useCallback(async () => {
    if (selected.length === 0) return;
    setLoading(true);
    try {
      const res = await fetchCompare({
        ingredientIds: selected.map((s) => s.id),
        radiusKm,
        includeDelivery,
      });
      setResult(res);
    } finally {
      setLoading(false);
    }
  }, [selected, radiusKm, includeDelivery]);

  const runFrequency = useCallback(
    async (frequency: string) => {
      setLoading(true);
      try {
        const res = await fetchFrequencyRun(frequency, radiusKm, includeDelivery);
        // Reflect the loaded run as editable chips, so what's shown IS what's
        // compared — the user can trim any ingredient they didn't want.
        if (res) {
          setSelected(
            res.ingredients.map((i) => ({ id: i.ingredient_id, name: i.canonical_name_en })),
          );
        }
        setResult(res);
      } finally {
        setLoading(false);
      }
    },
    [radiusKm, includeDelivery],
  );

  const basket = result?.basket_summary ?? null;
  const grouped = result ? groupByWinningStore(result.ingredients) : [];

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4">
      <style>{`
        @media print {
          .print-hide { display: none !important; }
          .print-store-card { box-shadow: none !important; border: 1px solid #000 !important; break-inside: avoid; }
          .print-store-heading { font-size: 1.5rem !important; font-weight: 700 !important; color: #000 !important; }
          .print-root, .print-root * { color: #000 !important; }
        }
      `}</style>

      <header className="print-hide space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </header>

      {/* Controls */}
      <Card className="print-hide print:hidden">
        <CardHeader>
          <CardTitle>{t("whatBuying")}</CardTitle>
          <CardDescription>{t("controlsDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Ingredient multi-select */}
          <div className="relative">
            <Input
              value={query}
              placeholder={t("searchPlaceholder")}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setSearchOpen(searchResults.length > 0)}
            />
            {searchOpen ? (
              <div className="bg-popover absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border shadow-md">
                {searchResults.map((hit) => (
                  <button
                    key={hit.id}
                    type="button"
                    className="hover:bg-accent hover:text-accent-foreground flex w-full flex-col items-start px-3 py-2 text-left text-sm"
                    onClick={() => addIngredient(hit)}
                  >
                    <span className="font-medium">{hit.canonical_name_en}</span>
                    {hit.matched_text && hit.matched_text !== hit.canonical_name_en ? (
                      <span className="text-muted-foreground text-xs">
                        {t("matched", { text: hit.matched_text })}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          {selected.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selected.map((s) => (
                <Badge key={s.id} variant="secondary" className="gap-1 py-1">
                  {s.name}
                  <button
                    type="button"
                    aria-label={t("remove", { name: s.name })}
                    className="hover:text-destructive ml-1 rounded-sm"
                    onClick={() => removeIngredient(s.id)}
                  >
                    ×
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">{t("noneSelected")}</p>
          )}

          {/* Load by frequency */}
          <div className="space-y-2">
            <p className="text-sm font-medium">{t("loadByFrequency")}</p>
            <p className="text-muted-foreground text-xs">{t("freqHelp")}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="default" onClick={() => runFrequency("weekly")} disabled={loading}>
                {t("thisWeekRun")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => runFrequency("monthly")}
                disabled={loading}
              >
                {t("monthlyRun")}
              </Button>
              {FREQUENCIES.filter((f) => f.value !== "weekly" && f.value !== "monthly").map((f) => (
                <Button
                  key={f.value}
                  variant="outline"
                  onClick={() => runFrequency(f.value)}
                  disabled={loading}
                >
                  {labels.frequency(f.value)}
                </Button>
              ))}
            </div>
          </div>

          {/* Radius presets */}
          <div className="space-y-2">
            <p className="text-sm font-medium">{t("howFar")}</p>
            <div className="flex flex-wrap gap-2">
              {RADIUS_PRESETS.map((preset) => (
                <Button
                  key={preset.km}
                  variant={radiusKm === preset.km ? "default" : "outline"}
                  onClick={() => setRadiusKm(preset.km)}
                >
                  {preset.label}
                </Button>
              ))}
              <Button
                variant={radiusKm === null ? "default" : "outline"}
                onClick={() => setRadiusKm(null)}
              >
                {t("anyDistance")}
              </Button>
            </div>
          </div>

          {/* Delivery + Compare */}
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={() => setIncludeDelivery((v) => !v)}>
              {includeDelivery ? t("deliveryOn") : t("deliveryOff")}
            </Button>
            <Button onClick={runCompare} disabled={selected.length === 0 || loading}>
              {loading ? t("comparing") : t("compare")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result ? (
        <div className="print-root space-y-6 print:block">
          <div className="print-hide flex items-center justify-between">
            <h2 className="text-xl font-semibold">{t("results")}</h2>
            <Button variant="outline" onClick={() => window.print()}>
              {t("printRun")}
            </Button>
          </div>

          {result.store_count === 0 ? (
            <Card>
              <CardContent className="text-muted-foreground py-6 text-sm">
                {t("noStoreData")}
              </CardContent>
            </Card>
          ) : null}

          {/* Basket summary banner */}
          {basket ? (
            <Card className="border-primary/40">
              <CardHeader>
                <CardTitle>{t("basketSummary")}</CardTitle>
                <CardDescription>
                  {t("singleStore")}:{" "}
                  {basket.single_store
                    ? `${basket.single_store.store_name} ${dollars(basket.single_store.total_cents)}`
                    : "—"}{" "}
                  · {t("bestPerItem")}: {dollars(basket.best_per_item_total_cents)}
                  {basket.split && basket.split.secondary
                    ? ` · ${t("splitSaves")} ${dollars(basket.split.savings_vs_single_cents)}`
                    : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-muted-foreground text-xs uppercase">{t("singleStore")}</p>
                    <p className="text-lg font-semibold">
                      {basket.single_store ? dollars(basket.single_store.total_cents) : "—"}
                    </p>
                    {basket.single_store ? (
                      <p className="text-muted-foreground text-xs">
                        {basket.single_store.store_name}
                      </p>
                    ) : null}
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs uppercase">{t("bestPerItem")}</p>
                    <p className="text-lg font-semibold">
                      {dollars(basket.best_per_item_total_cents)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs uppercase">{t("splitTrip")}</p>
                    {basket.split && basket.split.secondary ? (
                      <>
                        <p className="text-lg font-semibold">
                          {t("saves", {
                            amount: dollars(basket.split.savings_vs_single_cents),
                          })}
                        </p>
                        <p className="text-muted-foreground text-xs">
                          {basket.split.primary.store_name} + {basket.split.secondary.store_name}
                        </p>
                      </>
                    ) : (
                      <p className="text-lg font-semibold">—</p>
                    )}
                  </div>
                </div>
                {result.notes.length > 0 ? (
                  <div className="space-y-1">
                    {result.notes.map((note, i) => (
                      <p key={i} className="text-muted-foreground text-xs">
                        {note}
                      </p>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {/* Grouped by winning store */}
          {grouped.length > 0 ? (
            <div className="space-y-4">
              {grouped.map((group) => (
                <Card key={group.storeName} className="print-store-card">
                  <CardHeader>
                    <CardTitle className="print-store-heading">{group.storeName}</CardTitle>
                    <CardDescription>
                      {t("cheapestForItems", { count: group.items.length })}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="divide-y">
                    {group.items.map(({ ingredient, winner }) => (
                      <div
                        key={ingredient.ingredient_id}
                        className="flex flex-wrap items-baseline justify-between gap-2 py-2"
                      >
                        <div className="min-w-0">
                          <p className="font-medium">{ingredient.canonical_name_en}</p>
                          <p className="text-muted-foreground text-xs">
                            {winner.pack_desc} · {optionMeta(winner, t)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="whitespace-nowrap font-semibold">
                            {dollars(winner.unit_price_cents)}/{labels.unit(winner.base_unit)}
                          </span>
                          <ConfidenceBadge option={winner} />
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}

          {/* Per-ingredient all options */}
          <div className="print-hide space-y-4">
            <h3 className="text-lg font-semibold">{t("allOptions")}</h3>
            {result.ingredients.map((ingredient) => {
              const options = ingredient.options;
              const onlyOne = options.length === 1;
              return (
                <Card key={ingredient.ingredient_id}>
                  <CardHeader>
                    <CardTitle className="text-base">{ingredient.canonical_name_en}</CardTitle>
                    {onlyOne ? (
                      <CardDescription>{t("onlyOneStore")}</CardDescription>
                    ) : null}
                  </CardHeader>
                  <CardContent>
                    {options.length === 0 ? (
                      <p className="text-muted-foreground text-sm">
                        {t("noFreshPrices")}{" "}
                        <Link href="/dashboard/prices/bulk" className="underline">
                          {t("logOne")}
                        </Link>
                      </p>
                    ) : (
                      <div className="divide-y">
                        {options.map((opt) => (
                          <div
                            key={opt.store_id}
                            className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm"
                          >
                            <div className="min-w-0">
                              <span className="font-medium">{opt.store_name}</span>
                              <span className="text-muted-foreground ml-2 text-xs">
                                {opt.distance_km != null
                                  ? t("kmValue", { km: opt.distance_km.toFixed(0) })
                                  : t("distanceNa")}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="whitespace-nowrap">
                                {dollars(opt.unit_price_cents)}/{labels.unit(ingredient.base_unit)}
                              </span>
                              <span className="text-muted-foreground whitespace-nowrap text-xs">
                                {t("savesVsWorst", { pct: opt.savings_vs_worst_pct.toFixed(0) })}
                              </span>
                              <ConfidenceBadge option={opt} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
