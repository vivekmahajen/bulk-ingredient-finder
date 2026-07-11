"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Ingredient } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export default function IngredientsPage() {
  const [ingredients, setIngredients] = useState<Ingredient[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ingredients</h1>
          <p className="text-muted-foreground">
            {ingredients ? `${ingredients.length} in your catalog` : "Loading…"}
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/ingredients/new">＋ Add ingredient</Link>
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-3">
        {ingredients?.map((ing) => (
          <Card key={ing.id}>
            <CardContent className="flex items-center justify-between gap-4 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{ing.canonical_name_en}</span>
                  {ing.display_name.toLowerCase() !== ing.canonical_name_en.toLowerCase() && (
                    <span className="text-sm text-muted-foreground">· {ing.display_name}</span>
                  )}
                  {ing.needs_review && <Badge variant="warning">Needs review</Badge>}
                </div>
                {ing.aliases.length > 0 && (
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    also searchable as: {ing.aliases.map((a) => a.alias).join(", ")}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge variant="secondary">{ing.category}</Badge>
                <Badge variant="outline">{ing.purchase_frequency.replace("_", " ")}</Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {ingredients?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No ingredients yet.{" "}
          <Link className="underline" href="/dashboard/ingredients/new">
            Add your first one
          </Link>
          .
        </p>
      )}
    </div>
  );
}
