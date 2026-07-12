import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import es from "../messages/es.json";
import hi from "../messages/hi.json";

/** Every nested key path in an object, sorted — so we compare shape, not order. */
function keyPaths(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object") return [prefix];
  const out: string[] = [];
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${k}` : k;
    out.push(...keyPaths(v, path));
  }
  return out.sort();
}

describe("i18n catalog parity", () => {
  const enKeys = keyPaths(en);

  it("es has exactly the same keys as en", () => {
    const esKeys = keyPaths(es);
    expect(esKeys).toEqual(enKeys);
  });

  it("hi has exactly the same keys as en", () => {
    const hiKeys = keyPaths(hi);
    expect(hiKeys).toEqual(enKeys);
  });

  it("includes the invoices namespace", () => {
    expect(enKeys.some((k) => k.startsWith("invoices."))).toBe(true);
  });
});
