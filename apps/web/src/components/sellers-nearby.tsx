"use client";

import { useCallback, useEffect, useState } from "react";
import {
  baseQuantity,
  dollars,
  fetchCompare,
  isBulk,
  kmToMiles,
  milesToKm,
  RADIUS_PRESETS_MI,
  type IngredientCompare,
  type StoreOption,
} from "@/lib/compare";
import { kindLabel, type Store, type StoreKind } from "@/lib/stores";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StoreFormDialog } from "@/components/store-form-dialog";
import { LogPriceDialog } from "@/components/log-price-dialog";
import { useToast } from "@/components/ui/use-toast";

interface SellersNearbyProps {
  ingredientId: string;
  ingredientName: string;
}

const CONFIDENCE_VARIANT: Record<string, "default" | "secondary" | "warning"> = {
  high: "default",
  medium: "secondary",
  low: "warning",
};

function distanceLabel(o: StoreOption): string {
  if (o.distance_km == null) return o.delivers ? "delivery" : "—";
  return `${kmToMiles(o.distance_km).toFixed(1)} mi`;
}

/** Human pack size in the base unit, e.g. "20 kg". */
function packSize(o: StoreOption): string | null {
  const qty = baseQuantity(o);
  if (qty == null) return null;
  return `${qty % 1 === 0 ? qty : qty.toFixed(1)} ${o.base_unit}`;
}

export function SellersNearby({ ingredientId, ingredientName }: SellersNearbyProps) {
  const { toast } = useToast();

  const [miles, setMiles] = useState(25);
  const [milesInput, setMilesInput] = useState("25");
  const [includeDelivery, setIncludeDelivery] = useState(true);
  const [bulkOnly, setBulkOnly] = useState(false);

  const [data, setData] = useState<IngredientCompare | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [preselectStoreId, setPreselectStoreId] = useState<string | undefined>(undefined);

  const load = useCallback(() => {
    setLoading(true);
    void fetchCompare({
      ingredientIds: [ingredientId],
      radiusKm: milesToKm(miles),
      includeDelivery,
    }).then((res) => {
      setLoading(false);
      if (res === null) {
        setData(null);
        setNotes(["Couldn't load sellers. Try again."]);
        return;
      }
      setData(res.ingredients[0] ?? null);
      setNotes(res.notes);
    });
  }, [ingredientId, miles, includeDelivery]);

  useEffect(() => {
    load();
  }, [load]);

  function applyMiles(value: number) {
    if (!Number.isFinite(value) || value <= 0) return;
    setMiles(value);
    setMilesInput(String(value));
  }

  const allOptions = data?.options ?? [];
  const options = bulkOnly ? allOptions.filter(isBulk) : allOptions;
  const cheapest = options[0] ?? null;

  function onSellerAdded(s: Store) {
    setPreselectStoreId(s.id);
    toast({
      title: "Seller added",
      description: `${s.name} is now in the system. Log its bulk price to compare it.`,
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Sellers &amp; bulk pricing</CardTitle>
            <CardDescription>
              Every supplier pricing {ingredientName}, cheapest first — within your radius or that
              delivers.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <StoreFormDialog
              onSaved={onSellerAdded}
              trigger={
                <Button variant="outline" size="sm">
                  ＋ Add a seller
                </Button>
              }
            />
            <LogPriceDialog
              ingredientId={ingredientId}
              ingredientName={ingredientName}
              storeId={preselectStoreId}
              onLogged={load}
              trigger={<Button size="sm">Log a bulk price</Button>}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Controls */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label htmlFor="radius-mi" className="text-muted-foreground text-xs font-medium">
              Within (miles)
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="radius-mi"
                type="number"
                inputMode="decimal"
                min="1"
                value={milesInput}
                onChange={(e) => setMilesInput(e.target.value)}
                onBlur={() => applyMiles(Number(milesInput.trim()))}
                onKeyDown={(e) => {
                  if (e.key === "Enter") applyMiles(Number(milesInput.trim()));
                }}
                className="w-24"
              />
              <div className="flex gap-1">
                {RADIUS_PRESETS_MI.map((p) => (
                  <Button
                    key={p.miles}
                    type="button"
                    size="sm"
                    variant={miles === p.miles ? "default" : "outline"}
                    onClick={() => applyMiles(p.miles)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={includeDelivery ? "default" : "outline"}
              onClick={() => setIncludeDelivery((v) => !v)}
            >
              {includeDelivery ? "✓ " : ""}Include delivery
            </Button>
            <Button
              type="button"
              size="sm"
              variant={bulkOnly ? "default" : "outline"}
              onClick={() => setBulkOnly((v) => !v)}
            >
              {bulkOnly ? "✓ " : ""}Bulk packs only
            </Button>
          </div>
        </div>

        {/* Cheapest highlight */}
        {cheapest && (
          <div className="bg-muted/50 rounded-lg border p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <span className="text-muted-foreground text-xs">
                  Cheapest within {miles} mi{bulkOnly ? " (bulk)" : ""}
                </span>
                <div className="text-xl font-semibold">
                  {dollars(cheapest.unit_price_cents)}/{cheapest.base_unit} @ {cheapest.store_name}
                </div>
                <div className="text-muted-foreground text-xs">
                  {dollars(cheapest.price_cents)} for {cheapest.pack_desc}
                  {cheapest.savings_vs_worst_pct > 0 &&
                    ` · ${cheapest.savings_vs_worst_pct.toFixed(0)}% under the priciest`}
                </div>
              </div>
              <div className="text-muted-foreground text-right text-xs">
                {distanceLabel(cheapest)}
                {cheapest.delivers && (
                  <>
                    {" · "}
                    <Badge variant="secondary">delivers</Badge>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Seller table */}
        {loading ? (
          <p className="text-muted-foreground text-sm">Loading sellers…</p>
        ) : options.length === 0 ? (
          <div className="text-muted-foreground space-y-2 text-sm">
            <p>
              {allOptions.length > 0 && bulkOnly
                ? "No bulk-sized packs among the sellers in range. Turn off “Bulk packs only” to see all."
                : "No sellers found for this ingredient in range."}
            </p>
            {notes.map((n, i) => (
              <p key={i} className="text-xs">
                {n}
              </p>
            ))}
            {allOptions.length === 0 && (
              <p className="text-xs">
                Add a seller and log its bulk price, or widen the radius / enable delivery. Distances
                need your org home location set (Stores → set location).
              </p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Seller</TableHead>
                  <TableHead className="text-right">Unit price</TableHead>
                  <TableHead>Pack</TableHead>
                  <TableHead className="text-right">Pack price</TableHead>
                  <TableHead className="text-right">Distance</TableHead>
                  <TableHead>Freshness</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {options.map((o, i) => (
                  <TableRow key={o.store_id} className={i === 0 ? "font-medium" : ""}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span>{o.store_name}</span>
                        {i === 0 && <Badge>cheapest</Badge>}
                        {isBulk(o) && <Badge variant="secondary">bulk</Badge>}
                      </div>
                      <div className="text-muted-foreground text-xs">
                        {o.store_kind ? kindLabel(o.store_kind as StoreKind) : "—"}
                        {o.brand ? ` · ${o.brand}` : ""}
                        {o.delivers ? " · delivers" : ""}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {dollars(o.unit_price_cents)}/{o.base_unit}
                    </TableCell>
                    <TableCell className="text-xs">
                      {o.pack_desc}
                      {packSize(o) && (
                        <span className="text-muted-foreground"> ({packSize(o)})</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">{dollars(o.price_cents)}</TableCell>
                    <TableCell className="text-right text-xs">{distanceLabel(o)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Badge variant={CONFIDENCE_VARIANT[o.confidence] ?? "secondary"}>
                          {o.confidence}
                        </Badge>
                        <span className="text-muted-foreground text-xs">{o.observed_at}</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
