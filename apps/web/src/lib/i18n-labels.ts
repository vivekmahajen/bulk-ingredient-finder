/**
 * Locale-aware labels for the app's fixed vocabularies (categories, units,
 * purchase cadence, store kinds, months, price confidence/source). Values are
 * the canonical enum strings; labels come from the `enums` namespace in
 * `messages/*.json`. Unknown values fall back to the raw value so nothing ever
 * renders blank.
 */

import { useTranslations } from "next-intl";

type Group = "category" | "unit" | "frequency" | "storeKind" | "confidence" | "source" | "month";

export interface EnumLabels {
  category: (v: string) => string;
  unit: (v: string) => string;
  frequency: (v: string) => string;
  storeKind: (v: string) => string;
  confidence: (v: string) => string;
  source: (v: string) => string;
  month: (v: string) => string;
}

export function useEnumLabels(): EnumLabels {
  const t = useTranslations("enums");
  const label = (group: Group, v: string): string => {
    const key = `${group}.${v}`;
    return t.has(key) ? t(key) : v;
  };
  return {
    category: (v) => label("category", v),
    unit: (v) => label("unit", v),
    frequency: (v) => label("frequency", v),
    storeKind: (v) => label("storeKind", v),
    confidence: (v) => label("confidence", v),
    source: (v) => label("source", v),
    month: (v) => label("month", v),
  };
}
