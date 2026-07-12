/** Compare / answer-screen types + client for PR-7. */

import { apiGet, apiPost } from "@/lib/api";

export interface StoreOption {
  store_id: string;
  store_name: string;
  store_kind: string | null;
  brand: string | null;
  unit_price_cents: number;
  base_unit: string;
  pack_desc: string;
  price_cents: number;
  observed_at: string;
  age_days: number;
  distance_km: number | null;
  delivers: boolean;
  confidence: "high" | "medium" | "low";
  savings_vs_worst_pct: number;
}

export interface IngredientCompare {
  ingredient_id: string;
  canonical_name_en: string;
  base_unit: string;
  best_store_id: string | null;
  options: StoreOption[];
}

export interface BasketStoreTotal {
  store_id: string;
  store_name: string;
  total_cents: number;
  covers: number;
}

export interface SplitSuggestion {
  primary: BasketStoreTotal;
  secondary: BasketStoreTotal | null;
  total_cents: number;
  savings_vs_single_cents: number;
}

export interface BasketSummary {
  single_store: BasketStoreTotal | null;
  best_per_item_total_cents: number;
  split: SplitSuggestion | null;
  savings_best_vs_single_cents: number;
}

export interface CompareResponse {
  ingredients: IngredientCompare[];
  basket_summary: BasketSummary | null;
  radius_km: number | null;
  include_delivery: boolean;
  store_count: number;
  notes: string[];
}

/** Radius presets, labeled per the spec. */
export const RADIUS_PRESETS: ReadonlyArray<{ km: number; label: string }> = [
  { km: 10, label: "Local" },
  { km: 25, label: "Redding run" },
  { km: 60, label: "60 km" },
  { km: 150, label: "Sacramento run" },
];

export const FREQUENCIES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "daily", label: "Daily" },
  { value: "twice_weekly", label: "2×/week" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];

export function dollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

const KM_PER_MILE = 1.60934;

export function milesToKm(miles: number): number {
  return miles * KM_PER_MILE;
}

export function kmToMiles(km: number): number {
  return km / KM_PER_MILE;
}

/** Radius presets for a single-ingredient "sellers near me" view, in miles. */
export const RADIUS_PRESETS_MI: ReadonlyArray<{ miles: number; label: string }> = [
  { miles: 10, label: "10 mi" },
  { miles: 25, label: "25 mi" },
  { miles: 50, label: "50 mi" },
  { miles: 100, label: "100 mi" },
];

/**
 * The pack quantity in the option's base unit (kg / l / each), derived exactly
 * from price ÷ unit-price. e.g. a $52 pack at $2.60/kg is 20 kg.
 */
export function baseQuantity(o: StoreOption): number | null {
  if (!o.unit_price_cents) return null;
  return o.price_cents / o.unit_price_cents;
}

/**
 * Whether an option represents a genuinely bulk pack. There is no explicit
 * "bulk" flag on a price, so we treat it as a threshold on the pack size in the
 * comparable base unit: ≥ 5 kg, ≥ 4 L, or ≥ 6 units.
 */
const BULK_THRESHOLDS: Record<string, number> = { kg: 5, l: 4, each: 6 };

export function isBulk(o: StoreOption): boolean {
  const qty = baseQuantity(o);
  if (qty === null) return false;
  const threshold = BULK_THRESHOLDS[o.base_unit] ?? 0;
  return qty >= threshold;
}

interface CompareParams {
  ingredientIds: string[];
  radiusKm?: number | null;
  includeDelivery: boolean;
}

export async function fetchCompare(p: CompareParams): Promise<CompareResponse | null> {
  const params = new URLSearchParams();
  p.ingredientIds.forEach((id) => params.append("ingredient_ids", id));
  if (p.radiusKm != null) params.set("radius_km", String(p.radiusKm));
  params.set("include_delivery", String(p.includeDelivery));
  const res = await apiGet<CompareResponse>(`/api/v1/compare?${params.toString()}`);
  return res.ok ? res.data : null;
}

export async function fetchFrequencyRun(
  frequency: string,
  radiusKm: number | null,
  includeDelivery: boolean,
): Promise<CompareResponse | null> {
  const params = new URLSearchParams({ frequency, include_delivery: String(includeDelivery) });
  if (radiusKm != null) params.set("radius_km", String(radiusKm));
  const res = await apiGet<CompareResponse>(`/api/v1/compare/frequency-run?${params.toString()}`);
  return res.ok ? res.data : null;
}

export async function fetchCompareWithQuantities(
  ingredientIds: string[],
  quantities: Record<string, number>,
  radiusKm: number | null,
  includeDelivery: boolean,
): Promise<CompareResponse | null> {
  const res = await apiPost<CompareResponse>("/api/v1/compare", {
    ingredient_ids: ingredientIds,
    quantities,
    radius_km: radiusKm,
    include_delivery: includeDelivery,
  });
  return res.ok ? res.data : null;
}
