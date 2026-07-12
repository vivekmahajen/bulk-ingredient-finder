/**
 * Parse a pasted/uploaded ingredient table into API-ready `IngredientCreate`
 * rows. Two shapes are supported:
 *
 *  1. Header-mapped — the first row names the columns (e.g. a forecast
 *     spreadsheet with `Ingredient, …, Category, Purchase as, Order cadence`).
 *     Columns are matched by name, values are normalized (category lower-cased,
 *     cadence → purchase_frequency, unit inferred from the pack description),
 *     and unrelated columns (monthly forecast, annual, per-serving) are ignored
 *     — the per-serving/pack text is preserved in `notes`.
 *  2. Positional — no header: `name, category, unit, frequency?, language?,
 *     par_level?` (tab- or comma-separated).
 */

import {
  CATEGORIES,
  DEFAULT_UNITS,
  FREQUENCIES,
  type Category,
  type DefaultUnit,
  type PurchaseFrequency,
} from "@/lib/types";

export interface IngredientCreate {
  display_name: string;
  source_lang?: string | null;
  category: Category;
  default_unit: DefaultUnit;
  purchase_frequency: PurchaseFrequency;
  par_level?: number | null;
  notes?: string | null;
}

export interface PreviewRow {
  raw: string;
  parsed?: IngredientCreate;
  error?: string;
}

export interface ParseResult {
  headerMapped: boolean;
  rows: PreviewRow[];
}

const FREQ_VALUES = FREQUENCIES.map((f) => f.value) as readonly string[];

function detectDelimiter(line: string): "\t" | "," {
  return line.includes("\t") ? "\t" : ",";
}

/** Split a row, honoring RFC-4180 double-quotes for comma-delimited input. */
function splitRow(line: string, delim: "\t" | ","): string[] {
  if (delim === "\t") return line.split("\t");
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else inQuotes = false;
      } else cur += c;
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      out.push(cur);
      cur = "";
    } else cur += c;
  }
  out.push(cur);
  return out;
}

export function normalizeCategory(value: string): Category | null {
  const s = value.trim().toLowerCase();
  return (CATEGORIES as readonly string[]).includes(s) ? (s as Category) : null;
}

/** Map a free-text order cadence ("2×/week", "Weekly", "Monthly", …). */
export function normalizeFrequency(value: string): PurchaseFrequency {
  const s = value.trim().toLowerCase().replace(/\s+/g, "");
  if (/(2|two|twice)[x×]?\/?(week|wk)/.test(s)) return "twice_weekly";
  if (/daily|everyday/.test(s)) return "daily";
  if (/biweek|fortnight|every2week/.test(s)) return "biweekly";
  if (/month/.test(s)) return "monthly";
  if (/quarter/.test(s)) return "quarterly";
  if (/week/.test(s)) return "weekly";
  return "weekly";
}

/** Infer the base unit from a pack description ("40 lb case", "Gallon", …). */
export function inferUnit(purchaseAs: string): DefaultUnit {
  const s = purchaseAs.toLowerCase();
  if (/gallon|quart|litre|liter|(^|\s)ml(\s|$)|(^|\s)l(\s|$)/.test(s)) return "l";
  if (/\bkg\b|gram|(^|\s)g(\s|$)|\blb\b|\boz\b|pound|bulk|block|jug/.test(s)) return "kg";
  if (/case/.test(s)) return "case";
  if (/bag|sack/.test(s)) return "bag";
  return "each";
}

interface HeaderCols {
  name: number;
  category: number;
  cadence: number;
  purchase: number;
  serving: number;
  vendor: number;
  website: number;
}

function findCol(headers: string[], ...needles: string[]): number {
  const lower = headers.map((h) => h.trim().toLowerCase());
  for (const needle of needles) {
    const i = lower.findIndex((h) => h.includes(needle));
    if (i >= 0) return i;
  }
  return -1;
}

function parseHeaderRow(line: string, delim: "\t" | ",", cols: HeaderCols): PreviewRow {
  const cells = splitRow(line, delim).map((c) => c.trim());
  const at = (idx: number): string => (idx >= 0 ? (cells[idx] ?? "") : "");

  const name = at(cols.name);
  if (name.length === 0) return { raw: line, error: "name is required" };

  const catRaw = at(cols.category);
  const category = normalizeCategory(catRaw);
  if (category === null)
    return { raw: line, error: `unknown category "${catRaw}" (use ${CATEGORIES.join("/")})` };

  const purchaseAs = at(cols.purchase);
  const serving = at(cols.serving);
  const default_unit = inferUnit(purchaseAs);
  const purchase_frequency = normalizeFrequency(at(cols.cadence));

  const vendor = at(cols.vendor);
  const website = at(cols.website);

  const noteParts: string[] = [];
  if (purchaseAs) noteParts.push(`Purchase as: ${purchaseAs}`);
  if (serving) noteParts.push(`~${serving} g/ml per serving`);
  if (vendor) noteParts.push(`Vendor: ${vendor}`);
  if (website) noteParts.push(`Website: ${website}`);

  const parsed: IngredientCreate = { display_name: name, category, default_unit, purchase_frequency };
  if (noteParts.length > 0) parsed.notes = noteParts.join(" · ");

  return { raw: `${name}  ·  ${category}  ·  ${default_unit}  ·  ${purchase_frequency}`, parsed };
}

function parsePositional(line: string, delim: "\t" | ","): PreviewRow {
  const cells = splitRow(line, delim).map((c) => c.trim());
  const [name, catStr, unitStr, freqStr, langStr, parStr] = cells;

  if (name === undefined || name.length === 0) return { raw: line, error: "name is required" };
  const category = catStr !== undefined ? normalizeCategory(catStr) : null;
  if (category === null)
    return { raw: line, error: `category must be one of ${CATEGORIES.join(", ")}` };
  if (unitStr === undefined || !(DEFAULT_UNITS as readonly string[]).includes(unitStr))
    return { raw: line, error: `unit must be one of ${DEFAULT_UNITS.join(", ")}` };

  let purchase_frequency: PurchaseFrequency = "weekly";
  if (freqStr !== undefined && freqStr.length > 0) {
    if (!FREQ_VALUES.includes(freqStr))
      return { raw: line, error: `frequency must be one of ${FREQ_VALUES.join(", ")}` };
    purchase_frequency = freqStr as PurchaseFrequency;
  }

  let par_level: number | null = null;
  if (parStr !== undefined && parStr.length > 0) {
    const n = Number(parStr);
    if (!Number.isFinite(n) || n < 0) return { raw: line, error: "par_level must be a number ≥ 0" };
    par_level = n;
  }

  const parsed: IngredientCreate = {
    display_name: name,
    category,
    default_unit: unitStr as DefaultUnit,
    purchase_frequency,
    par_level,
  };
  if (langStr !== undefined && langStr.length > 0) parsed.source_lang = langStr;
  return { raw: line, parsed };
}

/** True when the first row looks like column headers rather than data. */
function looksLikeHeader(cells: string[]): boolean {
  const lower = cells.map((c) => c.trim().toLowerCase());
  return lower.some((c) => c === "ingredient" || c === "name") && lower.includes("category");
}

export function parseIngredientTable(text: string): ParseResult {
  const lines = text
    .split("\n")
    .map((l) => l.replace(/\r$/, ""))
    .filter((l) => l.trim().length > 0);
  if (lines.length === 0) return { headerMapped: false, rows: [] };

  const delim = detectDelimiter(lines[0]);
  const firstCells = splitRow(lines[0], delim).map((c) => c.trim());

  if (looksLikeHeader(firstCells)) {
    const cols: HeaderCols = {
      name: findCol(firstCells, "ingredient", "name"),
      category: findCol(firstCells, "category"),
      cadence: findCol(firstCells, "order cadence", "cadence", "frequency"),
      purchase: findCol(firstCells, "purchase as", "purchase", "pack"),
      serving: findCol(firstCells, "per serving", "serving"),
      vendor: findCol(firstCells, "recommended vendor", "vendor", "supplier"),
      website: findCol(firstCells, "website", "url", "site"),
    };
    return {
      headerMapped: true,
      rows: lines.slice(1).map((line) => parseHeaderRow(line, delim, cols)),
    };
  }

  return { headerMapped: false, rows: lines.map((line) => parsePositional(line, delim)) };
}
