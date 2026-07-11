import { apiGet } from "@/lib/api";
import type { BestPrice } from "@/lib/format";
import type { Category, PurchaseFrequency } from "@/lib/types";

export interface SearchHit {
  id: string;
  canonical_name_en: string;
  display_name: string;
  source_lang: string;
  category: Category;
  default_unit: string;
  purchase_frequency: PurchaseFrequency;
  needs_review: boolean;
  score: number;
  matched_text: string;
  matched_kind: string;
  via_translation: boolean;
  best_price: BestPrice | null;
}

export interface SearchResponse {
  query: string;
  effective_query: string;
  via_translation: boolean;
  results: SearchHit[];
}

export interface SearchFilters {
  category?: Category;
  frequency?: PurchaseFrequency;
  limit?: number;
}

export async function searchIngredients(
  q: string,
  filters: SearchFilters = {},
): Promise<SearchResponse | null> {
  const params = new URLSearchParams({ q });
  if (filters.category) params.set("category", filters.category);
  if (filters.frequency) params.set("frequency", filters.frequency);
  params.set("limit", String(filters.limit ?? 20));
  const res = await apiGet<SearchResponse>(`/api/v1/search/ingredients?${params.toString()}`);
  return res.ok ? res.data : null;
}
