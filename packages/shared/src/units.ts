/**
 * Unit conversion + price normalization.
 *
 * Mirrors `apps/api/app/units.py` — keep the factor tables in sync.
 *
 * Every purchasable pack is normalized to a price per **base unit**, where the
 * base unit depends on the pack's physical dimension:
 *   - mass   -> price per kilogram (kg)
 *   - volume -> price per liter    (l)
 *   - count  -> price per each     (each)
 *
 * Canonical conversion factors (exact, from the spec):
 *   lb  -> kg : 0.45359237
 *   oz  -> g  : 28.349523      (=> oz -> kg : 0.028349523)
 *   gal -> l  : 3.785411784
 */

export const LB_TO_KG = 0.45359237;
export const OZ_TO_G = 28.349523;
export const GAL_TO_L = 3.785411784;

export type Dimension = "mass" | "volume" | "count";

export const PACK_UNITS = ["kg", "g", "lb", "oz", "l", "ml", "gal", "each"] as const;
export type PackUnit = (typeof PACK_UNITS)[number];

export const BASE_UNIT: Record<Dimension, PackUnit> = {
  mass: "kg",
  volume: "l",
  count: "each",
};

export const UNIT_DIMENSION: Record<PackUnit, Dimension> = {
  kg: "mass",
  g: "mass",
  lb: "mass",
  oz: "mass",
  l: "volume",
  ml: "volume",
  gal: "volume",
  each: "count",
};

/** Multiply a quantity in the given unit by this factor to get the base unit. */
export const TO_BASE_FACTOR: Record<PackUnit, number> = {
  kg: 1,
  g: 0.001,
  lb: LB_TO_KG,
  oz: OZ_TO_G / 1000, // oz -> g -> kg
  l: 1,
  ml: 0.001,
  gal: GAL_TO_L,
  each: 1,
};

export function dimensionOf(unit: PackUnit): Dimension {
  return UNIT_DIMENSION[unit];
}

export function baseUnitOf(unit: PackUnit): PackUnit {
  return BASE_UNIT[dimensionOf(unit)];
}

export function toBaseQuantity(qty: number, unit: PackUnit): number {
  return qty * TO_BASE_FACTOR[unit];
}

export function fromBaseQuantity(qtyBase: number, unit: PackUnit): number {
  return qtyBase / TO_BASE_FACTOR[unit];
}

/**
 * Normalized price: cents per base unit for the pack's dimension.
 * `priceCents` buys `packQty` × `packUnit`; returns cents per kg / l / each.
 */
export function cToUnitPricePerBase(
  priceCents: number,
  packQty: number,
  packUnit: PackUnit,
): number {
  const baseQty = toBaseQuantity(packQty, packUnit);
  if (baseQty === 0) throw new Error("packQty must be non-zero");
  return priceCents / baseQty;
}
