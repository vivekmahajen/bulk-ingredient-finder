/** Web price-discovery types + client. Results are ESTIMATES from the open web. */

import { apiGet } from "@/lib/api";

export interface DiscoveredSeller {
  name: string;
  price_text: string | null;
  price_cents: number | null;
  pack_desc: string | null;
  pack_qty: number | null;
  pack_unit: string | null;
  unit_price_cents: number | null;
  base_unit: string | null;
  url: string | null;
  location: string | null;
  distance_note: string | null;
  snippet: string | null;
}

export interface DiscoverResponse {
  configured: boolean;
  query: string;
  sellers: DiscoveredSeller[];
  notes: string[];
  disclaimer: string;
}

export async function discoverPrices(
  ingredientId: string,
  opts: { radiusMiles: number; location?: string },
): Promise<DiscoverResponse | null> {
  const params = new URLSearchParams({ radius_miles: String(opts.radiusMiles) });
  if (opts.location && opts.location.trim().length > 0) {
    params.set("location", opts.location.trim());
  }
  const res = await apiGet<DiscoverResponse>(
    `/api/v1/ingredients/${ingredientId}/discover-prices?${params.toString()}`,
  );
  return res.ok ? res.data : null;
}
