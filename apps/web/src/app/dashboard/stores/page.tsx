"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { kindLabel, type Store } from "@/lib/stores";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StoreFormDialog } from "@/components/store-form-dialog";

export default function StoresPage() {
  const [stores, setStores] = useState<Store[] | null>(null);

  const load = useCallback(() => {
    apiGet<Store[]>("/api/v1/stores").then((res) => {
      if (res.ok) setStores(res.data);
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Stores</h1>
          <p className="text-muted-foreground">
            {stores ? `${stores.length} suppliers` : "Loading…"}
          </p>
        </div>
        <StoreFormDialog onSaved={load} trigger={<Button>＋ Add store</Button>} />
      </div>

      <div className="grid gap-3">
        {stores?.map((store) => (
          <Card key={store.id} className="hover:border-foreground/30 transition-colors">
            <CardContent className="flex items-center justify-between gap-4 py-4">
              <Link href={`/dashboard/stores/${store.id}`} className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{store.name}</span>
                  <Badge variant="secondary">{kindLabel(store.kind)}</Badge>
                  {!store.geocoded && <Badge variant="warning">no location</Badge>}
                </div>
                <p className="text-muted-foreground mt-1 text-xs">
                  {[store.city, store.state].filter(Boolean).join(", ")}
                  {store.delivers && store.delivery_days?.length
                    ? ` · delivers ${store.delivery_days.join(", ")}`
                    : store.delivers
                      ? " · delivers"
                      : ""}
                  {store.min_order ? ` · min $${store.min_order}` : ""}
                </p>
              </Link>
              <div className="flex shrink-0 items-center gap-3">
                {store.distance_km != null && (
                  <span className="text-muted-foreground text-sm">
                    {store.distance_km.toFixed(0)} km
                  </span>
                )}
                {store.website && (
                  <a
                    className="text-sm underline"
                    href={store.website}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Website
                  </a>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {stores?.length === 0 && (
        <p className="text-muted-foreground text-sm">No stores yet. Add your first supplier.</p>
      )}
    </div>
  );
}
