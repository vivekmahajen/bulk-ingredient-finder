/** Display helpers for prices and dates — always showing date + source honesty. */

export interface BestPrice {
  price_cents: number;
  unit_price_cents: number;
  base_unit: string;
  store_name: string;
  observed_at: string;
}

/** e.g. "$2.41/kg @ CHEF'STORE Redding · 12d ago" */
export function formatBestPrice(p: BestPrice, now: Date = new Date()): string {
  const perUnit = `$${(p.unit_price_cents / 100).toFixed(2)}/${p.base_unit}`;
  return `${perUnit} @ ${p.store_name} · ${formatAge(p.observed_at, now)}`;
}

export function ageDays(observedAt: string, now: Date = new Date()): number {
  const observed = new Date(observedAt + "T00:00:00Z");
  const ms = now.getTime() - observed.getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

export function formatAge(observedAt: string, now: Date = new Date()): string {
  const days = ageDays(observedAt, now);
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  return `${days}d ago`;
}

/** Highlight the substring of `text` that matches `query` (case-insensitive). */
export function highlightMatch(
  text: string,
  query: string,
): { pre: string; hit: string; post: string } {
  const idx = text.toLowerCase().indexOf(query.trim().toLowerCase());
  if (!query.trim() || idx === -1) return { pre: text, hit: "", post: "" };
  return {
    pre: text.slice(0, idx),
    hit: text.slice(idx, idx + query.trim().length),
    post: text.slice(idx + query.trim().length),
  };
}
