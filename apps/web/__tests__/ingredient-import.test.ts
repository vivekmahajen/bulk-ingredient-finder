import { describe, expect, it } from "vitest";
import {
  inferUnit,
  normalizeCategory,
  normalizeFrequency,
  parseIngredientTable,
} from "@/lib/ingredient-import";

// A slice of the real forecast spreadsheet (tab-separated, with header row).
const FORECAST = [
  "Ingredient\tg/ml per serving\tJan\tFeb\tMar\tApr\tMay\tJun\tJul\tAug\tSep\tOct\tNov\tDec\tAnnual\tCategory\tPurchase as\tOrder cadence",
  "Chicken (boneless)\t165\t49.4\t37.9\t45.0\t71.3\t100.4\t81.1\t125.2\t121.5\t79.9\t66.7\t73.7\t53.8\t906\tProtein\t40 lb case\t2×/week",
  "Whole milk\t240\t61.8\t47.4\t56.3\t89.2\t125.6\t101.4\t156.5\t152.0\t99.9\t83.4\t92.1\t67.3\t1,133\tDairy\tGallon\t2×/week",
  "Basmati rice (dry)\t75\t71.8\t55.2\t65.4\t103.7\t146.0\t118.0\t182.0\t176.7\t116.2\t97.0\t107.1\t78.2\t1,317\tStaple\t20 lb bags\tMonthly",
  "Onions\t100\t71.5\t54.9\t65.1\t103.2\t145.3\t117.4\t181.2\t175.9\t115.6\t96.5\t106.6\t77.8\t1,311\tProduce\t50 lb sacks\tWeekly",
].join("\n");

describe("parseIngredientTable — forecast spreadsheet (header-mapped)", () => {
  const { headerMapped, rows } = parseIngredientTable(FORECAST);

  it("detects the header row and maps by column name", () => {
    expect(headerMapped).toBe(true);
    expect(rows).toHaveLength(4);
    expect(rows.every((r) => r.parsed !== undefined)).toBe(true);
  });

  it("maps name, category, unit (inferred), and cadence; ignores forecast columns", () => {
    const chicken = rows[0].parsed!;
    expect(chicken.display_name).toBe("Chicken (boneless)");
    expect(chicken.category).toBe("protein");
    expect(chicken.default_unit).toBe("kg"); // "40 lb case" → mass base
    expect(chicken.purchase_frequency).toBe("twice_weekly"); // "2×/week"
    expect(chicken.notes).toContain("40 lb case");
    expect(chicken.notes).toContain("165");

    expect(rows[1].parsed!.default_unit).toBe("l"); // Whole milk / Gallon
    expect(rows[2].parsed!.purchase_frequency).toBe("monthly"); // Basmati rice
    expect(rows[3].parsed!.category).toBe("produce"); // Onions
    expect(rows[3].parsed!.purchase_frequency).toBe("weekly");
  });
});

describe("value normalizers", () => {
  it("categories are case-insensitive and validated", () => {
    expect(normalizeCategory("Protein")).toBe("protein");
    expect(normalizeCategory("DAIRY")).toBe("dairy");
    expect(normalizeCategory("Frozen")).toBe("frozen");
    expect(normalizeCategory("nonsense")).toBeNull();
  });

  it("order cadence maps to purchase_frequency", () => {
    expect(normalizeFrequency("2×/week")).toBe("twice_weekly");
    expect(normalizeFrequency("2x/week")).toBe("twice_weekly");
    expect(normalizeFrequency("Weekly")).toBe("weekly");
    expect(normalizeFrequency("Monthly")).toBe("monthly");
    expect(normalizeFrequency("Biweekly")).toBe("biweekly");
    expect(normalizeFrequency("")).toBe("weekly"); // sensible default
  });

  it("infers a base unit from the pack description", () => {
    expect(inferUnit("40 lb case")).toBe("kg");
    expect(inferUnit("Gallon")).toBe("l");
    expect(inferUnit("Quart/case")).toBe("l");
    expect(inferUnit("Case / #10 cans")).toBe("case");
    expect(inferUnit("5 kg blocks")).toBe("kg");
  });
});

describe("parseIngredientTable — positional fallback (no header)", () => {
  it("parses the simple name/category/unit format", () => {
    const { headerMapped, rows } = parseIngredientTable(
      ["Paneer\tdairy\tkg\ttwice_weekly", "Salt\tstaple\tkg"].join("\n"),
    );
    expect(headerMapped).toBe(false);
    expect(rows[0].parsed).toMatchObject({
      display_name: "Paneer",
      category: "dairy",
      default_unit: "kg",
      purchase_frequency: "twice_weekly",
    });
    expect(rows[1].parsed!.purchase_frequency).toBe("weekly"); // default
  });

  it("reports a clear error for a bad category", () => {
    const { rows } = parseIngredientTable("Widget\tgadget\tkg");
    expect(rows[0].parsed).toBeUndefined();
    expect(rows[0].error).toContain("category");
  });
});
