/** Price domain types + constants for PR-6. */

export type PackUnit = "kg" | "g" | "lb" | "oz" | "l" | "ml" | "gal" | "each";
export type PriceSource = "invoice" | "shelf" | "quote" | "website" | "manual";

export const PACK_UNITS: readonly PackUnit[] = ["kg", "g", "lb", "oz", "l", "ml", "gal", "each"];
export const PRICE_SOURCES: ReadonlyArray<{ value: PriceSource; label: string }> = [
  { value: "invoice", label: "Invoice" },
  { value: "shelf", label: "Shelf" },
  { value: "quote", label: "Quote" },
  { value: "website", label: "Website" },
  { value: "manual", label: "Manual" },
];

export interface PriceRead {
  id: string;
  ingredient_id: string;
  store_id: string;
  brand: string | null;
  pack_desc: string;
  pack_qty: number;
  pack_unit: PackUnit;
  price_cents: number;
  currency: string;
  observed_at: string;
  source: PriceSource;
  unit_price_cents: number | null;
  base_unit: string;
  age_days: number;
  stale: boolean;
  warnings: string[];
}

export interface PriceCreate {
  ingredient_id: string;
  store_id: string;
  brand?: string;
  pack_desc: string;
  pack_qty: number;
  pack_unit: PackUnit;
  price_cents: number;
  observed_at?: string;
  source: PriceSource;
}

export interface BulkRowResult {
  index: number;
  ok: boolean;
  id: string | null;
  warnings: string[];
  error: string | null;
}

export interface BulkResult {
  created: number;
  failed: number;
  results: BulkRowResult[];
}

export interface PriceHistoryPoint {
  observed_at: string;
  price_cents: number;
  pack_desc: string;
  unit_price_cents: number | null;
  base_unit: string;
  source: PriceSource;
  age_days: number;
  stale: boolean;
}

export interface StoreSeries {
  store_id: string;
  store_name: string;
  points: PriceHistoryPoint[];
}

export interface PriceHistory {
  ingredient_id: string;
  series: StoreSeries[];
}

/** Parse dollars (e.g. "52.00" or "$52") into integer cents. */
export function dollarsToCents(input: string): number | null {
  const cleaned = input.replace(/[$,\s]/g, "");
  if (!cleaned) return null;
  const value = Number(cleaned);
  if (!Number.isFinite(value)) return null;
  return Math.round(value * 100);
}
