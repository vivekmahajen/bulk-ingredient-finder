"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import {
  PACK_UNITS,
  PRICE_SOURCES,
  dollarsToCents,
  type PackUnit,
  type PriceCreate,
  type PriceRead,
  type PriceSource,
} from "@/lib/prices";
import { searchIngredients } from "@/lib/search";
import type { Store } from "@/lib/stores";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";

interface LogPriceDialogProps {
  ingredientId?: string;
  ingredientName?: string;
  storeId?: string;
  trigger: React.ReactNode;
  onLogged?: (p: PriceRead) => void;
}

interface IngredientOption {
  id: string;
  name: string;
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function LogPriceDialog({
  ingredientId,
  ingredientName,
  storeId,
  trigger,
  onLogged,
}: LogPriceDialogProps) {
  const { toast } = useToast();

  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Ingredient
  const [ingredient, setIngredient] = useState<IngredientOption | null>(
    ingredientId !== undefined && ingredientName !== undefined
      ? { id: ingredientId, name: ingredientName }
      : null,
  );
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<IngredientOption[]>([]);
  const [searching, setSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);

  // Store
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<string>(storeId ?? "");

  // Fields
  const [brand, setBrand] = useState("");
  const [packDesc, setPackDesc] = useState("");
  const [packQty, setPackQty] = useState("");
  const [packUnit, setPackUnit] = useState<PackUnit>("lb");
  const [price, setPrice] = useState("");
  const [observedAt, setObservedAt] = useState(todayISO());
  const [source, setSource] = useState<PriceSource>("invoice");
  const [warnings, setWarnings] = useState<string[]>([]);

  const readOnlyIngredient = ingredientName !== undefined;

  // Load stores on mount.
  useEffect(() => {
    let active = true;
    void apiGet<Store[]>("/api/v1/stores").then((res) => {
      if (active && res.ok) setStores(res.data);
    });
    return () => {
      active = false;
    };
  }, []);

  // Debounced ingredient search (200ms).
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (readOnlyIngredient) return;
    const q = query.trim();
    if (q.length === 0) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void searchIngredients(q).then((resp) => {
        setSearching(false);
        if (resp === null) {
          setResults([]);
          return;
        }
        setResults(resp.results.map((r) => ({ id: r.id, name: r.canonical_name_en })));
        setShowResults(true);
      });
    }, 200);
    return () => {
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
  }, [query, readOnlyIngredient]);

  function resetForNextEntry() {
    setBrand("");
    setPackDesc("");
    setPackQty("");
    setPrice("");
    setWarnings([]);
  }

  function resetAll() {
    if (!readOnlyIngredient) {
      setIngredient(
        ingredientId !== undefined && ingredientName !== undefined
          ? { id: ingredientId, name: ingredientName }
          : null,
      );
      setQuery("");
      setResults([]);
    }
    setSelectedStore(storeId ?? "");
    setBrand("");
    setPackDesc("");
    setPackQty("");
    setPackUnit("lb");
    setPrice("");
    setObservedAt(todayISO());
    setSource("invoice");
    setWarnings([]);
  }

  function selectIngredient(opt: IngredientOption) {
    setIngredient(opt);
    setShowResults(false);
    setQuery("");
  }

  /** Returns the built body, or null (after toasting) when validation fails. */
  function buildBody(): PriceCreate | null {
    if (ingredient === null) {
      toast({
        title: "Ingredient required",
        description: "Search for and select an ingredient first.",
        variant: "destructive",
      });
      return null;
    }
    if (selectedStore.length === 0) {
      toast({
        title: "Store required",
        description: "Pick a store before saving.",
        variant: "destructive",
      });
      return null;
    }
    const qty = Number(packQty.trim());
    if (!Number.isFinite(qty) || qty <= 0) {
      toast({
        title: "Invalid pack quantity",
        description: "Pack quantity must be a number greater than 0.",
        variant: "destructive",
      });
      return null;
    }
    const priceCents = dollarsToCents(price);
    if (priceCents === null || priceCents <= 0) {
      toast({
        title: "Invalid price",
        description: "Enter a price greater than $0.",
        variant: "destructive",
      });
      return null;
    }
    if (packDesc.trim().length === 0) {
      toast({
        title: "Pack description required",
        description: 'Describe the pack, e.g. "20 lb bag".',
        variant: "destructive",
      });
      return null;
    }

    const body: PriceCreate = {
      ingredient_id: ingredient.id,
      store_id: selectedStore,
      pack_desc: packDesc.trim(),
      pack_qty: qty,
      pack_unit: packUnit,
      price_cents: priceCents,
      observed_at: observedAt,
      source,
    };
    const trimmedBrand = brand.trim();
    if (trimmedBrand.length > 0) body.brand = trimmedBrand;
    return body;
  }

  async function submit(keepOpen: boolean) {
    const body = buildBody();
    if (body === null) return;

    setSubmitting(true);
    const res = await apiPost<PriceRead>("/api/v1/prices", body);
    setSubmitting(false);

    if (!res.ok) {
      toast({
        title: res.problem.title,
        description: res.problem.detail,
        variant: "destructive",
      });
      return;
    }

    onLogged?.(res.data);

    if (res.data.warnings.length > 0) {
      setWarnings(res.data.warnings);
      toast({
        title: "Price saved with warnings",
        description: res.data.warnings.join(" "),
      });
    } else {
      setWarnings([]);
      toast({ title: "Price logged" });
    }

    if (keepOpen) {
      resetForNextEntry();
    } else {
      setOpen(false);
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void submit(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) resetAll();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Log a price</DialogTitle>
          <DialogDescription>Record a supplier price for an ingredient.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Ingredient */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Ingredient</label>
            {readOnlyIngredient ? (
              <Input value={ingredientName} readOnly disabled />
            ) : ingredient !== null ? (
              <div className="flex items-center gap-2">
                <Input value={ingredient.name} readOnly />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIngredient(null)}
                >
                  Change
                </Button>
              </div>
            ) : (
              <div className="relative">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setShowResults(true)}
                  placeholder="Search ingredients…"
                  autoComplete="off"
                />
                {showResults && query.trim().length > 0 && (
                  <div className="bg-popover text-popover-foreground absolute z-50 mt-1 max-h-56 w-full overflow-y-auto rounded-md border p-1 shadow-md">
                    {searching ? (
                      <p className="text-muted-foreground px-2 py-1.5 text-sm">Searching…</p>
                    ) : results.length === 0 ? (
                      <p className="text-muted-foreground px-2 py-1.5 text-sm">No matches.</p>
                    ) : (
                      results.map((r) => (
                        <button
                          key={r.id}
                          type="button"
                          className="hover:bg-accent hover:text-accent-foreground w-full rounded-sm px-2 py-1.5 text-left text-sm"
                          onClick={() => selectIngredient(r)}
                        >
                          {r.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Store */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Store</label>
            <Select value={selectedStore} onValueChange={setSelectedStore}>
              <SelectTrigger>
                <SelectValue placeholder="Select store" />
              </SelectTrigger>
              <SelectContent>
                {stores.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Brand */}
          <div className="space-y-1">
            <label htmlFor="price-brand" className="text-sm font-medium">
              Brand <span className="text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="price-brand"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="e.g. Laxmi"
            />
          </div>

          {/* Pack description */}
          <div className="space-y-1">
            <label htmlFor="price-pack-desc" className="text-sm font-medium">
              Pack description
            </label>
            <Input
              id="price-pack-desc"
              value={packDesc}
              onChange={(e) => setPackDesc(e.target.value)}
              placeholder="20 lb bag"
            />
          </div>

          {/* Pack qty + unit */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label htmlFor="price-pack-qty" className="text-sm font-medium">
                Pack qty
              </label>
              <Input
                id="price-pack-qty"
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                value={packQty}
                onChange={(e) => setPackQty(e.target.value)}
                placeholder="20"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Pack unit</label>
              <Select value={packUnit} onValueChange={(v) => setPackUnit(v as PackUnit)}>
                <SelectTrigger>
                  <SelectValue placeholder="Unit" />
                </SelectTrigger>
                <SelectContent>
                  {PACK_UNITS.map((u) => (
                    <SelectItem key={u} value={u}>
                      {u}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Price + date */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label htmlFor="price-amount" className="text-sm font-medium">
                Price ($)
              </label>
              <Input
                id="price-amount"
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="52.00"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="price-date" className="text-sm font-medium">
                Date
              </label>
              <input
                id="price-date"
                type="date"
                value={observedAt}
                onChange={(e) => setObservedAt(e.target.value)}
                className="border-input focus-visible:ring-ring flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
          </div>

          {/* Source */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Source</label>
            <Select value={source} onValueChange={(v) => setSource(v as PriceSource)}>
              <SelectTrigger>
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                {PRICE_SOURCES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {warnings.length > 0 && (
            <div className="rounded-md bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
              <ul className="list-inside list-disc space-y-0.5">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={submitting}
              onClick={() => void submit(true)}
            >
              Save &amp; add another
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
