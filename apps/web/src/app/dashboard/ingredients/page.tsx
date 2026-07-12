"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useEnumLabels } from "@/lib/i18n-labels";
import type { Ingredient } from "@/lib/types";
import { searchIngredients, type SearchHit } from "@/lib/search";
import { formatBestPrice, highlightMatch } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export default function IngredientsPage() {
  const t = useTranslations("ingredients");
  const labels = useEnumLabels();
  const [ingredients, setIngredients] = useState<Ingredient[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [viaTranslation, setViaTranslation] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    apiGet<Ingredient[]>("/api/v1/ingredients").then((res) => {
      if (!active) return;
      if (res.ok) setIngredients(res.data);
      else setError(res.problem.detail ?? res.problem.title);
    });
    return () => {
      active = false;
    };
  }, []);

  const onSearch = useCallback((q: string) => {
    setQuery(q);
    if (debounce.current) clearTimeout(debounce.current);
    if (!q.trim()) {
      setHits(null);
      setViaTranslation(false);
      return;
    }
    debounce.current = setTimeout(async () => {
      const res = await searchIngredients(q);
      setHits(res?.results ?? []);
      setViaTranslation(res?.via_translation ?? false);
    }, 200);
  }, []);

  const searching = query.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground">
            {ingredients ? t("inCatalog", { count: ingredients.length }) : t("loading")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <Link href="/dashboard/ingredients/bulk">⇪ {t("bulkUpload")}</Link>
          </Button>
          <Button asChild>
            <Link href="/dashboard/ingredients/new">＋ {t("add")}</Link>
          </Button>
        </div>
      </div>

      <Input
        value={query}
        onChange={(e) => onSearch(e.target.value)}
        placeholder={t("searchPlaceholder")}
      />
      {searching && viaTranslation && (
        <p className="text-muted-foreground text-xs">{t("matchedViaTranslation")}</p>
      )}

      {error && <p className="text-destructive text-sm">{error}</p>}

      {/* Search results (server-ranked) take over when a query is present. */}
      {searching ? (
        <div className="grid gap-3">
          {hits?.map((hit) => {
            const { pre, hit: h, post } = highlightMatch(hit.matched_text, query);
            return (
              <Card key={hit.id}>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{hit.canonical_name_en}</span>
                      {hit.matched_kind === "alias" && (
                        <span className="text-muted-foreground text-sm">
                          matched{" "}
                          <span>
                            {pre}
                            <mark className="rounded bg-amber-200 dark:bg-amber-900/60">{h}</mark>
                            {post}
                          </span>
                        </span>
                      )}
                      {hit.needs_review && <Badge variant="warning">{t("needsReview")}</Badge>}
                    </div>
                    {hit.best_price && (
                      <p className="text-muted-foreground mt-1 text-xs">
                        {formatBestPrice(hit.best_price)}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant="secondary">{labels.category(hit.category)}</Badge>
                    <Badge variant="outline">{labels.frequency(hit.purchase_frequency)}</Badge>
                  </div>
                </CardContent>
              </Card>
            );
          })}
          {hits?.length === 0 && (
            <p className="text-muted-foreground text-sm">{t("noMatches", { query })}</p>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {ingredients?.map((ing) => (
            <Link key={ing.id} href={`/dashboard/ingredients/${ing.id}`}>
              <Card className="hover:border-foreground/30 transition-colors">
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{ing.canonical_name_en}</span>
                      {ing.display_name.toLowerCase() !== ing.canonical_name_en.toLowerCase() && (
                        <span className="text-muted-foreground text-sm">· {ing.display_name}</span>
                      )}
                      {ing.needs_review && <Badge variant="warning">{t("needsReview")}</Badge>}
                    </div>
                    {ing.aliases.length > 0 && (
                      <p className="text-muted-foreground mt-1 truncate text-xs">
                        {t("alsoSearchableAs")} {ing.aliases.map((a) => a.alias).join(", ")}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant="secondary">{labels.category(ing.category)}</Badge>
                    <Badge variant="outline">{labels.frequency(ing.purchase_frequency)}</Badge>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
