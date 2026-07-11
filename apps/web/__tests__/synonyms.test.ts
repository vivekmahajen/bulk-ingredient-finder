import { describe, expect, it } from "vitest";
import { SYNONYM_GROUPS, findGroup } from "@rasoi/shared";

// Mirror of the Python drift test (apps/api/tests/test_synonyms.py). Both read
// packages/shared/culinary_synonyms.json, so the two sides cannot diverge.
const KNOWN_PAIRS: Array<[string, string]> = [
  ["haldi", "turmeric"],
  ["jeera", "cumin"],
  ["dhania", "coriander"],
  ["hing", "asafoetida"],
  ["methi", "fenugreek"],
  ["atta", "whole wheat flour"],
  ["maida", "all-purpose flour"],
  ["besan", "gram flour"],
  ["toor dal", "pigeon peas"],
  ["ghee", "clarified butter"],
  ["paneer", "indian cottage cheese"],
  ["elaichi", "cardamom"],
  ["kadi patta", "curry leaves"],
  ["palak", "spinach"],
  ["pyaz", "onion"],
  ["adrak", "ginger"],
  ["lehsun", "garlic"],
];

describe("culinary synonyms (shared, drift-guarded)", () => {
  it.each(KNOWN_PAIRS)("resolves %s → %s", (alias, canonical) => {
    expect(findGroup(alias)?.canonical_en).toBe(canonical);
  });

  it("is case-insensitive", () => {
    expect(findGroup("HALDI")).toBe(findGroup("haldi"));
  });

  it("loads a non-trivial group set with terms", () => {
    expect(SYNONYM_GROUPS.length).toBeGreaterThanOrEqual(20);
    expect(SYNONYM_GROUPS.every((g) => g.terms.length > 0)).toBe(true);
  });
});
