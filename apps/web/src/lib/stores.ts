/** Store domain types + option constants for PR-5. */

export type StoreKind =
  "broadline" | "cash_and_carry" | "ethnic_wholesale" | "produce_house" | "retail" | "online";

export interface Store {
  id: string;
  name: string;
  kind: StoreKind;
  address_line: string | null;
  city: string | null;
  state: string | null;
  postal: string | null;
  lat: number | null;
  lng: number | null;
  website: string | null;
  phone: string | null;
  delivers: boolean;
  delivery_days: string[] | null;
  min_order: number | null;
  notes: string | null;
  is_active: boolean;
  distance_km: number | null;
  geocoded: boolean;
}

export interface StorePriceRow {
  ingredient_id: string;
  canonical_name_en: string;
  display_name: string;
  price_cents: number;
  pack_desc: string;
  pack_qty: number;
  pack_unit: string;
  unit_price_cents: number | null;
  base_unit: string;
  observed_at: string;
  source: string;
}

export interface StoreWin {
  ingredient_id: string;
  canonical_name_en: string;
  unit_price_cents: number;
  observed_at: string;
}

export const STORE_KINDS: ReadonlyArray<{ value: StoreKind; label: string }> = [
  { value: "broadline", label: "Broadline" },
  { value: "cash_and_carry", label: "Cash & carry" },
  { value: "ethnic_wholesale", label: "Ethnic wholesale" },
  { value: "produce_house", label: "Produce house" },
  { value: "retail", label: "Retail" },
  { value: "online", label: "Online" },
];

export const DELIVERY_DAYS: readonly string[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function kindLabel(kind: StoreKind): string {
  return STORE_KINDS.find((k) => k.value === kind)?.label ?? kind;
}
