/** Domain types mirroring the API's Pydantic read schemas. */

export type Category =
  | "protein"
  | "dairy"
  | "produce"
  | "staple"
  | "spice"
  | "frozen"
  | "beverage"
  | "packaging"
  | "other";

export type DefaultUnit = "kg" | "g" | "l" | "ml" | "each" | "case" | "bag";

export type PurchaseFrequency =
  "daily" | "twice_weekly" | "weekly" | "biweekly" | "monthly" | "quarterly";

export type AliasKind = "translation" | "transliteration" | "synonym" | "user_alias";

export interface IngredientAlias {
  id: string;
  alias: string;
  lang: string;
  kind: AliasKind;
}

export interface Ingredient {
  id: string;
  canonical_name_en: string;
  display_name: string;
  source_lang: string;
  category: Category;
  default_unit: DefaultUnit;
  purchase_frequency: PurchaseFrequency;
  par_level: number | null;
  notes: string | null;
  is_active: boolean;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
  aliases: IngredientAlias[];
}

/** Language options, each rendered in its own script. */
export const LANGUAGES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "pa", label: "ਪੰਜਾਬੀ" },
  { value: "gu", label: "ગુજરાતી" },
  { value: "es", label: "Español" },
  { value: "zh", label: "中文" },
  { value: "vi", label: "Tiếng Việt" },
  { value: "ko", label: "한국어" },
  { value: "pt", label: "Português" },
];

export const CATEGORIES: readonly Category[] = [
  "protein",
  "dairy",
  "produce",
  "staple",
  "spice",
  "frozen",
  "beverage",
  "packaging",
  "other",
];

export const DEFAULT_UNITS: readonly DefaultUnit[] = ["kg", "g", "l", "ml", "each", "case", "bag"];

export const FREQUENCIES: ReadonlyArray<{ value: PurchaseFrequency; label: string }> = [
  { value: "daily", label: "Daily" },
  { value: "twice_weekly", label: "2×/week" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];
