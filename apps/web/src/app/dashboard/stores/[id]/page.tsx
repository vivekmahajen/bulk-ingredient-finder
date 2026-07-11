"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import { kindLabel, type Store, type StorePriceRow, type StoreWin } from "@/lib/stores";
import { ageDays, formatAge } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StoreFormDialog } from "@/components/store-form-dialog";

const STALE_DAYS = 45;

function addressText(store: Store): string {
  const cityLine = [store.city, [store.state, store.postal].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(", ");
  return [store.address_line, cityLine].filter(Boolean).join(", ");
}

export default function StoreDetailPage() {
  const { id } = useParams<{ id: string }>();

  const [store, setStore] = useState<Store | null>(null);
  const [prices, setPrices] = useState<StorePriceRow[]>([]);
  const [wins, setWins] = useState<StoreWin[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [storeRes, priceRes, winRes] = await Promise.all([
      apiGet<Store>(`/api/v1/stores/${id}`),
      apiGet<StorePriceRow[]>(`/api/v1/stores/${id}/prices`),
      apiGet<StoreWin[]>(`/api/v1/stores/${id}/wins`),
    ]);

    if (!storeRes.ok) {
      setNotFound(storeRes.status === 404);
      setStore(null);
      setLoading(false);
      return;
    }

    setNotFound(false);
    setStore(storeRes.data);
    setPrices(priceRes.ok ? priceRes.data : []);
    setWins(winRes.ok ? winRes.data : []);
    setLoading(false);
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const backLink = (
    <Link href="/dashboard/stores" className="text-muted-foreground text-sm hover:underline">
      ← All stores
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        {backLink}
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (notFound || !store) {
    return (
      <div className="space-y-6">
        {backLink}
        <Card>
          <CardHeader>
            <CardTitle>Store not found</CardTitle>
            <CardDescription>
              This supplier doesn&apos;t exist or may have been removed.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const address = addressText(store);

  return (
    <div className="space-y-6">
      {backLink}

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{store.name}</h1>
            <Badge variant="secondary">{kindLabel(store.kind)}</Badge>
            {!store.geocoded && <Badge variant="warning">no location</Badge>}
          </div>
          {address && <p className="text-muted-foreground text-sm">{address}</p>}
          <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            {store.website && (
              <a className="underline" href={store.website} target="_blank" rel="noreferrer">
                Website
              </a>
            )}
            {store.phone && <span>{store.phone}</span>}
            {store.delivers && (
              <span>
                Delivers
                {store.delivery_days?.length ? `: ${store.delivery_days.join(", ")}` : ""}
              </span>
            )}
            {store.min_order != null && <span>Min order ${store.min_order}</span>}
            {store.distance_km != null && <span>{store.distance_km.toFixed(1)} km away</span>}
          </div>
        </div>
        <StoreFormDialog
          store={store}
          onSaved={(s) => setStore(s)}
          trigger={<Button variant="outline">Edit</Button>}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Wins on (best current price)</CardTitle>
          <CardDescription>Categories where this store has the lowest unit price.</CardDescription>
        </CardHeader>
        <CardContent>
          {wins.length === 0 ? (
            <p className="text-muted-foreground text-sm">No categories won yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {wins.map((win) => (
                <Badge key={win.ingredient_id} variant="secondary">
                  {win.canonical_name_en}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Price history</CardTitle>
          <CardDescription>Every observation logged for this supplier.</CardDescription>
        </CardHeader>
        <CardContent>
          {prices.length === 0 ? (
            <div className="space-y-1">
              <p className="text-muted-foreground text-sm">No prices logged yet.</p>
              <p className="text-muted-foreground text-xs">
                Log a price to start comparing this store against others.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ingredient</TableHead>
                    <TableHead>Pack</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Unit price</TableHead>
                    <TableHead>Observed</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {prices.map((row, i) => {
                    const stale = ageDays(row.observed_at) > STALE_DAYS;
                    return (
                      <TableRow key={`${row.ingredient_id}-${row.observed_at}-${i}`}>
                        <TableCell className="font-medium">{row.display_name}</TableCell>
                        <TableCell className="text-muted-foreground">{row.pack_desc}</TableCell>
                        <TableCell>${(row.price_cents / 100).toFixed(2)}</TableCell>
                        <TableCell>
                          {row.unit_price_cents != null
                            ? `$${(row.unit_price_cents / 100).toFixed(2)}/${row.base_unit}`
                            : "—"}
                        </TableCell>
                        <TableCell>
                          {stale ? (
                            <div className="flex items-center gap-2">
                              <span>{formatAge(row.observed_at)}</span>
                              <Badge variant="warning">stale</Badge>
                            </div>
                          ) : (
                            formatAge(row.observed_at)
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{row.source}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
