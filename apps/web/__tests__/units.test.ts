import { describe, expect, it } from "vitest";
import {
  PACK_UNITS,
  baseUnitOf,
  cToUnitPricePerBase,
  fromBaseQuantity,
  toBaseQuantity,
  type PackUnit,
} from "@rasoi/shared";

describe("unit conversion (shared)", () => {
  it("round-trips every unit through its base", () => {
    for (const unit of PACK_UNITS) {
      for (const qty of [0.5, 1, 20, 999.9]) {
        const rt = fromBaseQuantity(toBaseQuantity(qty, unit), unit);
        expect(rt).toBeCloseTo(qty, 9);
      }
    }
  });

  it("maps units to the right base dimension", () => {
    expect(baseUnitOf("lb")).toBe("kg");
    expect(baseUnitOf("gal")).toBe("l");
    expect(baseUnitOf("each")).toBe("each");
  });

  it("normalizes a 20 lb bag at $52 to ~$5.73/kg (matches the API)", () => {
    const perKgCents = cToUnitPricePerBase(5200, 20, "lb" satisfies PackUnit);
    expect(Number((perKgCents / 100).toFixed(2))).toBe(5.73);
  });

  it("halves the unit price when the pack doubles", () => {
    const single = cToUnitPricePerBase(1000, 10, "kg");
    const double = cToUnitPricePerBase(1000, 20, "kg");
    expect(double).toBeCloseTo(single / 2, 9);
  });
});
