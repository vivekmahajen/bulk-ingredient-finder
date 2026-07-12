"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { apiPost } from "@/lib/api";
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
import { discoverPrices, type DiscoveredSeller, type DiscoverResponse } from "@/lib/discovery";
import { useEnumLabels } from "@/lib/i18n-labels";
import { PACK_UNITS, type PackUnit, type PriceCreate } from "@/lib/prices";
import { type Store } from "@/lib/stores";
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

function distanceLabel(o: StoreOption, deliveryWord: string): string {
  if (o.distance_km == null) return o.delivers ? deliveryWord : "—";
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
  const t = useTranslations("sellers");
  const tc = useTranslations("common");
  const labels = useEnumLabels();

  const [miles, setMiles] = useState(25);
  const [milesInput, setMilesInput] = useState("25");
  const [includeDelivery, setIncludeDelivery] = useState(true);
  const [bulkOnly, setBulkOnly] = useState(false);

  const [data, setData] = useState<IngredientCompare | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [preselectStoreId, setPreselectStoreId] = useState<string | undefined>(undefined);

  // Web price discovery (estimated, live search).
  const [webLocation, setWebLocation] = useState("");
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState<DiscoverResponse | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);

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
        setNotes([t("toastLoadFailed")]);
        return;
      }
      setData(res.ingredients[0] ?? null);
      setNotes(res.notes);
    });
  }, [ingredientId, miles, includeDelivery, t]);

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
      title: t("toastSellerAdded"),
      description: t("toastSellerAddedInSystem", { name: s.name }),
    });
  }

  async function runDiscovery() {
    setDiscovering(true);
    setDiscovered(null);
    const res = await discoverPrices(ingredientId, { radiusMiles: miles, location: webLocation });
    setDiscovering(false);
    if (res === null) {
      toast({
        title: t("toastWebFailed"),
        description: t("toastWebFailedDesc"),
        variant: "destructive",
      });
      return;
    }
    setDiscovered(res);
  }

  function sellerKey(s: DiscoveredSeller, i: number): string {
    return `${i}:${s.name}`;
  }

  function hasConcretePrice(s: DiscoveredSeller): boolean {
    return (
      s.price_cents != null &&
      s.price_cents > 0 &&
      s.pack_qty != null &&
      s.pack_qty > 0 &&
      s.pack_unit != null &&
      (PACK_UNITS as readonly string[]).includes(s.pack_unit)
    );
  }

  /** Create a store record from a discovered seller. Returns it, or null on error. */
  async function createStore(s: DiscoveredSeller): Promise<Store | null> {
    const res = await apiPost<Store>("/api/v1/stores", {
      name: s.name,
      kind: s.url ? "online" : "cash_and_carry",
      website: s.url ?? undefined,
      notes: s.location ?? undefined,
    });
    if (!res.ok) {
      toast({ title: res.problem.title, description: res.problem.detail, variant: "destructive" });
      return null;
    }
    return res.data;
  }

  /** Add the seller to the system (store only), no price. */
  async function addSellerOnly(s: DiscoveredSeller, key: string) {
    setSavingKey(key);
    try {
      const store = await createStore(s);
      if (store) {
        setPreselectStoreId(store.id);
        toast({
          title: t("toastSellerAdded"),
          description: t("toastSellerAddedStore", { name: s.name }),
        });
      }
    } finally {
      setSavingKey(null);
    }
  }

  /** Add the seller and log its web price so it flows into Compare. */
  async function saveSellerAndPrice(s: DiscoveredSeller, key: string) {
    setSavingKey(key);
    try {
      const store = await createStore(s);
      if (!store) return;
      const body: PriceCreate = {
        ingredient_id: ingredientId,
        store_id: store.id,
        pack_desc: s.pack_desc ?? `${s.pack_qty} ${s.pack_unit}`,
        pack_qty: s.pack_qty as number,
        pack_unit: s.pack_unit as PackUnit,
        price_cents: s.price_cents as number,
        source: "website",
      };
      const priceRes = await apiPost<unknown>("/api/v1/prices", body);
      if (!priceRes.ok) {
        toast({
          title: t("toastPriceNotSaved"),
          description: priceRes.problem.detail,
          variant: "destructive",
        });
      } else {
        toast({ title: t("toastSaved"), description: t("toastSavedDesc", { name: s.name }) });
        load();
      }
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{t("title")}</CardTitle>
            <CardDescription>{t("subtitle", { name: ingredientName })}</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <StoreFormDialog
              onSaved={onSellerAdded}
              trigger={
                <Button variant="outline" size="sm">
                  {t("addSeller")}
                </Button>
              }
            />
            <LogPriceDialog
              ingredientId={ingredientId}
              ingredientName={ingredientName}
              storeId={preselectStoreId}
              onLogged={load}
              trigger={<Button size="sm">{t("logBulkPrice")}</Button>}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Controls */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label htmlFor="radius-mi" className="text-muted-foreground text-xs font-medium">
              {t("within")}
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
              {includeDelivery ? "✓ " : ""}
              {t("includeDelivery")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={bulkOnly ? "default" : "outline"}
              onClick={() => setBulkOnly((v) => !v)}
            >
              {bulkOnly ? "✓ " : ""}
              {t("bulkOnly")}
            </Button>
          </div>
        </div>

        {/* Live web discovery — find sellers + prices on the web for this radius. */}
        <div className="flex flex-wrap items-end gap-2 rounded-md border border-dashed p-3">
          <div className="space-y-1">
            <label htmlFor="web-location" className="text-muted-foreground text-xs font-medium">
              {t("searchWebNear")}
            </label>
            <Input
              id="web-location"
              value={webLocation}
              onChange={(e) => setWebLocation(e.target.value)}
              placeholder={t("searchWebPlaceholder")}
              className="w-72"
            />
          </div>
          <Button type="button" onClick={() => void runDiscovery()} disabled={discovering}>
            {discovering ? t("searchingWeb") : t("findCheapest", { miles })}
          </Button>
          <p className="text-muted-foreground w-full text-xs">{t("webHint")}</p>
        </div>

        {/* Cheapest highlight */}
        {cheapest && (
          <div className="bg-muted/50 rounded-lg border p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <span className="text-muted-foreground text-xs">
                  {bulkOnly ? t("cheapestWithinBulk", { miles }) : t("cheapestWithin", { miles })}
                </span>
                <div className="text-xl font-semibold">
                  {dollars(cheapest.unit_price_cents)}/{cheapest.base_unit} @ {cheapest.store_name}
                </div>
                <div className="text-muted-foreground text-xs">
                  {t("forPack", {
                    price: dollars(cheapest.price_cents),
                    pack: cheapest.pack_desc,
                  })}
                  {cheapest.savings_vs_worst_pct > 0 &&
                    ` · ${t("underPriciest", { pct: cheapest.savings_vs_worst_pct.toFixed(0) })}`}
                </div>
              </div>
              <div className="text-muted-foreground text-right text-xs">
                {distanceLabel(cheapest, tc("delivery"))}
                {cheapest.delivers && (
                  <>
                    {" · "}
                    <Badge variant="secondary">{tc("delivers")}</Badge>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Seller table */}
        {loading ? (
          <p className="text-muted-foreground text-sm">{t("loadingSellers")}</p>
        ) : options.length === 0 ? (
          <div className="text-muted-foreground space-y-2 text-sm">
            <p>
              {allOptions.length > 0 && bulkOnly ? t("noBulkInRange") : t("noSellersInRange")}
            </p>
            {notes.map((n, i) => (
              <p key={i} className="text-xs">
                {n}
              </p>
            ))}
            {allOptions.length === 0 && <p className="text-xs">{t("addOrWidenHint")}</p>}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="text-muted-foreground mb-1 text-xs font-medium">
              {t("loggedPrices")}
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("colSeller")}</TableHead>
                  <TableHead className="text-right">{t("colUnitPrice")}</TableHead>
                  <TableHead>{t("colPack")}</TableHead>
                  <TableHead className="text-right">{t("colPackPrice")}</TableHead>
                  <TableHead className="text-right">{t("colDistance")}</TableHead>
                  <TableHead>{t("colFreshness")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {options.map((o, i) => (
                  <TableRow key={o.store_id} className={i === 0 ? "font-medium" : ""}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span>{o.store_name}</span>
                        {i === 0 && <Badge>{t("cheapest")}</Badge>}
                        {isBulk(o) && <Badge variant="secondary">{t("bulk")}</Badge>}
                      </div>
                      <div className="text-muted-foreground text-xs">
                        {o.store_kind ? labels.storeKind(o.store_kind) : "—"}
                        {o.brand ? ` · ${o.brand}` : ""}
                        {o.delivers ? ` · ${tc("delivers")}` : ""}
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
                    <TableCell className="text-right text-xs">
                      {distanceLabel(o, tc("delivery"))}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Badge variant={CONFIDENCE_VARIANT[o.confidence] ?? "secondary"}>
                          {labels.confidence(o.confidence)}
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

        {/* Discovered from the web */}
        {discovering && (
          <p className="text-muted-foreground text-sm">{t("searchingSellers")}</p>
        )}
        {discovered !== null && (
          <div className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">{t("fromWeb")}</h3>
              <Badge variant="warning">{tc("estimated")}</Badge>
            </div>

            {!discovered.configured ? (
              <div className="text-muted-foreground space-y-1 text-sm">
                <p>{t("notConfigured")}</p>
                {discovered.notes.map((n, i) => (
                  <p key={i} className="text-xs">
                    {n}
                  </p>
                ))}
              </div>
            ) : discovered.sellers.length === 0 ? (
              <div className="text-muted-foreground space-y-1 text-sm">
                <p>{t("noWebSellers")}</p>
                {discovered.notes.map((n, i) => (
                  <p key={i} className="text-xs">
                    {n}
                  </p>
                ))}
              </div>
            ) : (
              <>
                <ul className="divide-y">
                  {discovered.sellers.map((s, i) => {
                    const key = sellerKey(s, i);
                    const priced = hasConcretePrice(s);
                    return (
                      <li key={key} className="flex flex-wrap items-start justify-between gap-2 py-3">
                        <div className="min-w-0 space-y-0.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{s.name}</span>
                            {i === 0 && s.unit_price_cents != null && <Badge>{t("cheapest")}</Badge>}
                            {s.url && (
                              <a
                                href={s.url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary text-xs underline-offset-4 hover:underline"
                              >
                                {tc("source")} ↗
                              </a>
                            )}
                          </div>
                          <div className="text-muted-foreground text-xs">
                            {s.price_cents != null ? dollars(s.price_cents) : (s.price_text ?? t("priceNa"))}
                            {s.pack_desc ? ` · ${s.pack_desc}` : ""}
                            {s.unit_price_cents != null
                              ? ` · ${dollars(s.unit_price_cents)}/${s.base_unit}`
                              : ""}
                          </div>
                          {(s.location || s.distance_note) && (
                            <div className="text-muted-foreground text-xs">
                              {[s.location, s.distance_note].filter(Boolean).join(" · ")}
                            </div>
                          )}
                          {s.snippet && (
                            <p className="text-muted-foreground max-w-prose text-xs italic">
                              “{s.snippet}”
                            </p>
                          )}
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={savingKey === key}
                            onClick={() => void addSellerOnly(s, key)}
                          >
                            {savingKey === key ? tc("saving") : t("addSellerBtn")}
                          </Button>
                          {priced && (
                            <Button
                              type="button"
                              size="sm"
                              disabled={savingKey === key}
                              onClick={() => void saveSellerAndPrice(s, key)}
                            >
                              {t("savePrice")}
                            </Button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                {discovered.notes.map((n, i) => (
                  <p key={i} className="text-muted-foreground text-xs">
                    {n}
                  </p>
                ))}
                <p className="text-muted-foreground text-xs">{discovered.disclaimer}</p>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
