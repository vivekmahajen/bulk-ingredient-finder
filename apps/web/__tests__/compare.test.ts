import { describe, expect, it } from "vitest";
import {
  baseQuantity,
  isBulk,
  kmToMiles,
  milesToKm,
  type StoreOption,
} from "@/lib/compare";

function option(overrides: Partial<StoreOption>): StoreOption {
  return {
    store_id: "s1",
    store_name: "Test",
    store_kind: "cash_and_carry",
    brand: null,
    unit_price_cents: 260, // $2.60 / base unit
    base_unit: "kg",
    pack_desc: "20 kg bag",
    price_cents: 5200, // $52.00
    observed_at: "2026-07-01",
    age_days: 5,
    distance_km: 16.0934,
    delivers: false,
    confidence: "high",
    savings_vs_worst_pct: 30,
    ...overrides,
  };
}

describe("compare helpers", () => {
  it("converts miles <-> km round-trip", () => {
    expect(milesToKm(10)).toBeCloseTo(16.0934, 4);
    expect(kmToMiles(16.0934)).toBeCloseTo(10, 6);
    expect(kmToMiles(milesToKm(25))).toBeCloseTo(25, 9);
  });

  it("derives the base quantity as price / unit price", () => {
    expect(baseQuantity(option({}))).toBeCloseTo(20, 9); // 5200 / 260 = 20 kg
    expect(baseQuantity(option({ unit_price_cents: 0 }))).toBeNull();
  });

  it("flags bulk packs by base-unit threshold", () => {
    expect(isBulk(option({ base_unit: "kg", price_cents: 5200, unit_price_cents: 260 }))).toBe(true); // 20kg
    expect(isBulk(option({ base_unit: "kg", price_cents: 260, unit_price_cents: 260 }))).toBe(false); // 1kg
    expect(isBulk(option({ base_unit: "l", price_cents: 1000, unit_price_cents: 200 }))).toBe(true); // 5 L ≥ 4
    expect(isBulk(option({ base_unit: "each", price_cents: 1200, unit_price_cents: 100 }))).toBe(true); // 12 ea ≥ 6
    expect(isBulk(option({ base_unit: "each", price_cents: 300, unit_price_cents: 100 }))).toBe(false); // 3 ea
  });
});
